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
from ..tariff import TariffManager

_LOGGER = logging.getLogger(__name__)


class PhantomCostRemainderSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor tracking accumulated cost difference between upstream and total cost."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-minus"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_cost_entity: str,
        group_total_cost_entity: str,
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the cost remainder sensor."""
        super().__init__(config_entry_id, group_name, group_id, "cost_remainder")
        self.hass = hass
        self._upstream_cost_entity = upstream_cost_entity
        self._group_total_cost_entity = group_total_cost_entity
        self._tariff_manager = tariff_manager
        self._attr_name = "Cost Remainder"
        self._attr_native_unit_of_measurement = tariff_manager.currency
        self._currency_symbol = tariff_manager.currency_symbol
        self._last_upstream_cost = None
        self._last_total_cost = None
        self._accumulated_remainder = 0.0
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "currency_symbol": self._currency_symbol,
            "upstream_cost_entity": self._upstream_cost_entity,
            "group_total_cost_entity": self._group_total_cost_entity,
        }
        
        # Add tracking values
        if self._last_upstream_cost is not None:
            attrs["last_upstream_cost"] = self._last_upstream_cost
        if self._last_total_cost is not None:
            attrs["last_total_cost"] = self._last_total_cost
        
        # Get current values
        upstream_state = self.hass.states.get(self._upstream_cost_entity)
        total_state = self.hass.states.get(self._group_total_cost_entity)
        
        if upstream_state and upstream_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                current_upstream = float(upstream_state.state)
                attrs["current_upstream_cost"] = current_upstream
                
                # Calculate instantaneous difference
                if total_state and total_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    try:
                        current_total = float(total_state.state)
                        attrs["instantaneous_difference"] = current_upstream - current_total
                    except (ValueError, TypeError):
                        pass
            except (ValueError, TypeError):
                pass
                
        if total_state and total_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                attrs["current_group_total_cost"] = float(total_state.state)
            except (ValueError, TypeError):
                pass
                
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._accumulated_remainder = float(last_state.state)
                    self._attr_native_value = self._accumulated_remainder
                    self._attr_available = True
                    
                    # Restore tracking values
                    if "last_upstream_cost" in last_state.attributes:
                        self._last_upstream_cost = float(last_state.attributes["last_upstream_cost"])
                    if "last_total_cost" in last_state.attributes:
                        self._last_total_cost = float(last_state.attributes["last_total_cost"])
                    
                    _LOGGER.info(
                        "Restored cost remainder: %s %s",
                        self._accumulated_remainder,
                        self._currency_symbol
                    )
                except (ValueError, TypeError):
                    self._accumulated_remainder = 0.0
                    self._attr_native_value = 0.0
        else:
            self._accumulated_remainder = 0.0
            self._attr_native_value = 0.0
        
        # Track both cost entities
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._upstream_cost_entity, self._group_total_cost_entity],
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
        # Get upstream cost
        upstream_state = self.hass.states.get(self._upstream_cost_entity)
        if upstream_state is None or upstream_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(
                "Cost remainder '%s' - upstream cost entity %s is unavailable",
                self._group_name,
                self._upstream_cost_entity,
            )
            # Keep previous value
            return
            
        # Get group total cost
        total_state = self.hass.states.get(self._group_total_cost_entity)
        if total_state is None or total_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(
                "Cost remainder '%s' - group total cost entity %s is unavailable",
                self._group_name,
                self._group_total_cost_entity,
            )
            # Keep previous value
            return
        
        try:
            current_upstream_cost = float(upstream_state.state)
            current_total_cost = float(total_state.state)
            
            # Calculate deltas if we have previous values
            if self._last_upstream_cost is not None and self._last_total_cost is not None:
                upstream_delta = current_upstream_cost - self._last_upstream_cost
                total_delta = current_total_cost - self._last_total_cost
                
                # Calculate remainder delta (upstream increase - total increase)
                remainder_delta = upstream_delta - total_delta
                
                # Only accumulate positive remainder (when upstream increases more than total)
                if remainder_delta > 0:
                    self._accumulated_remainder += remainder_delta
                    _LOGGER.info(
                        "Cost remainder '%s' - upstream delta: %.3f, total delta: %.3f, remainder delta: %.3f, accumulated: %.3f %s",
                        self._group_name,
                        upstream_delta,
                        total_delta,
                        remainder_delta,
                        self._accumulated_remainder,
                        self._currency_symbol,
                    )
                else:
                    _LOGGER.debug(
                        "Cost remainder '%s' - not accumulating negative remainder: %.3f",
                        self._group_name,
                        remainder_delta,
                    )
            
            # Update tracking values
            self._last_upstream_cost = current_upstream_cost
            self._last_total_cost = current_total_cost
            self._attr_native_value = self._accumulated_remainder
            self._attr_available = True
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Error calculating cost remainder for '%s': %s (upstream: %s, total: %s)",
                self._group_name,
                err,
                upstream_state.state,
                total_state.state,
            )
            # Keep previous value
    
    async def async_reset(self) -> None:
        """Reset the cost remainder accumulator."""
        _LOGGER.info("Resetting cost remainder for group '%s'", self._group_name)
        self._accumulated_remainder = 0.0
        self._attr_native_value = 0.0
        # Keep the last values to continue tracking from current state
        self.async_write_ha_state()