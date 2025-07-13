"""Cost remainder sensor implementation for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .base import PhantomBaseSensor
from ..repairs import (
    async_create_sensor_unavailable_issue,
    async_delete_sensor_unavailable_issue,
    async_create_upstream_unavailable_issue,
    async_delete_upstream_unavailable_issue,
)

_LOGGER = logging.getLogger(__name__)


class PhantomCostRemainderSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor for cost remainder (upstream cost - sum of device costs)."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_cost_entity: str | None,
        device_cost_entities: list[str],
        currency: str,
        currency_symbol: str,
    ) -> None:
        """Initialize the cost remainder sensor."""
        super().__init__(config_entry_id, group_name, group_id, "cost_remainder")
        self.hass = hass
        self._upstream_cost_entity = upstream_cost_entity
        self._device_cost_entities = device_cost_entities
        # Update name and icon based on whether we have upstream entity
        if upstream_cost_entity:
            self._attr_name = "Cost Remainder"
            self._attr_icon = "mdi:cash-minus"
        else:
            self._attr_name = "Untracked Cost"
            self._attr_icon = "mdi:cash-remove"
        self._attr_native_unit_of_measurement = currency
        self._currency_symbol = currency_symbol
        self._upstream_issue_created = False
        self._devices_issue_created = False
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "currency_symbol": self._currency_symbol,
            "device_count": len(self._device_cost_entities),
        }
        if self._upstream_cost_entity:
            attrs["upstream_cost_entity"] = self._upstream_cost_entity
        else:
            attrs["info"] = "No upstream cost entity configured"
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._attr_native_value = float(last_state.state)
                    self._attr_available = True
                except (ValueError, TypeError):
                    pass
        
        # Track both upstream and device cost entities
        entities_to_track = []
        if self._upstream_cost_entity:
            entities_to_track.append(self._upstream_cost_entity)
        entities_to_track.extend(self._device_cost_entities)
        
        if entities_to_track:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    entities_to_track,
                    self._handle_state_change,
                )
            )
        
        # Initial update
        self._update_state()
    
    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entities."""
        # Only update if the new state is valid
        new_state = event.data.get("new_state")
        if new_state is not None:
            self._update_state()
            self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        # Get upstream cost value
        upstream_value = None
        if self._upstream_cost_entity:
            upstream_state = self.hass.states.get(self._upstream_cost_entity)
            _LOGGER.debug(
                "Cost remainder '%s' - upstream cost state: %s",
                self._group_name,
                upstream_state.state if upstream_state else "None",
            )
            if upstream_state and upstream_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    upstream_value = float(upstream_state.state)
                except (ValueError, TypeError):
                    pass
        
        if upstream_value is None and self._upstream_cost_entity:
            _LOGGER.debug(
                "Cost remainder '%s' - upstream value is None",
                self._group_name,
            )
            # Don't update if upstream is not available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = 0.0
            
            # Create upstream issue if not already created
            if not self._upstream_issue_created:
                async_create_upstream_unavailable_issue(
                    self.hass,
                    "cost_remainder",
                    "Upstream Cost Sensor",
                    self._group_name,
                    self._upstream_cost_entity
                )
                self._upstream_issue_created = True
            return
        else:
            # Delete upstream issue if it was created
            if self._upstream_issue_created:
                async_delete_upstream_unavailable_issue(
                    self.hass,
                    "cost_remainder",
                    "Upstream Cost Sensor", 
                    self._group_name
                )
                self._upstream_issue_created = False
        
        # Calculate total from device cost entities
        total = 0
        any_available = False
        unavailable_entities = []
        
        for entity_id in self._device_cost_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                unavailable_entities.append(entity_id)
                continue
                
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                any_available = True
                try:
                    value = float(state.state)
                    total += value
                    _LOGGER.debug(
                        "Cost remainder '%s' - device cost %s: %s",
                        self._group_name,
                        entity_id,
                        value,
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert state to float: %s", state.state)
            else:
                unavailable_entities.append(entity_id)
        
        if not any_available:
            _LOGGER.debug(
                "Cost remainder '%s' - no device costs available",
                self._group_name,
            )
            # Don't update if no devices are available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = 0.0
            
            # Create devices issue if not already created
            if not self._devices_issue_created:
                async_create_sensor_unavailable_issue(
                    self.hass,
                    "cost_remainder",
                    self._attr_name,
                    self._group_name,
                    unavailable_entities
                )
                self._devices_issue_created = True
        else:
            self._attr_available = True
            # If no upstream entity, show total device costs
            if self._upstream_cost_entity is None:
                # Show as positive value for untracked costs
                self._attr_native_value = total
                _LOGGER.debug(
                    "Untracked cost '%s' - total device costs: %s %s",
                    self._group_name,
                    total,
                    self._currency_symbol,
                )
            else:
                # Calculate remainder when we have upstream
                remainder = upstream_value - total
                
                # Cost remainder can be negative (overage) or positive (underage)
                self._attr_native_value = remainder
                _LOGGER.debug(
                    "Cost remainder '%s' - calculated: %s - %s = %s",
                    self._group_name,
                    upstream_value,
                    total,
                    self._attr_native_value,
                )
            
            # Delete devices issue if it was created
            if self._devices_issue_created:
                async_delete_sensor_unavailable_issue(
                    self.hass,
                    "cost_remainder",
                    self._attr_name,
                    self._group_name
                )
                self._devices_issue_created = False