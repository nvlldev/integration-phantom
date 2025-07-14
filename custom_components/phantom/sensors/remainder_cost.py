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

from .base import PhantomBaseSensor
from ..tariff import TariffManager

_LOGGER = logging.getLogger(__name__)


class PhantomCostRemainderSensor(PhantomBaseSensor):
    """Sensor showing instantaneous cost remainder (upstream cost - total cost)."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
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
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "currency_symbol": self._currency_symbol,
            "upstream_cost_entity": self._upstream_cost_entity,
            "group_total_cost_entity": self._group_total_cost_entity,
        }
        
        # Get current values to show in attributes
        upstream_state = self.hass.states.get(self._upstream_cost_entity)
        total_state = self.hass.states.get(self._group_total_cost_entity)
        
        if upstream_state and upstream_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                upstream_cost = float(upstream_state.state)
                attrs["upstream_cost"] = upstream_cost
            except (ValueError, TypeError):
                pass
                
        if total_state and total_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                total_cost = float(total_state.state)
                attrs["group_total_cost"] = total_cost
            except (ValueError, TypeError):
                pass
                
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
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
            # Show 0 when unavailable
            self._attr_available = True
            self._attr_native_value = 0.0
            return
            
        # Get group total cost
        total_state = self.hass.states.get(self._group_total_cost_entity)
        if total_state is None or total_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(
                "Cost remainder '%s' - group total cost entity %s is unavailable",
                self._group_name,
                self._group_total_cost_entity,
            )
            # Show 0 when unavailable
            self._attr_available = True
            self._attr_native_value = 0.0
            return
        
        try:
            upstream_cost = float(upstream_state.state)
            total_cost = float(total_state.state)
            
            # Calculate instantaneous remainder (upstream - total)
            remainder = upstream_cost - total_cost
            
            self._attr_native_value = remainder
            self._attr_available = True
            
            _LOGGER.debug(
                "Cost remainder '%s' = upstream %.2f - total %.2f = %.2f %s",
                self._group_name,
                upstream_cost,
                total_cost,
                remainder,
                self._currency_symbol,
            )
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Error calculating cost remainder for '%s': %s (upstream: %s, total: %s)",
                self._group_name,
                err,
                upstream_state.state,
                total_state.state,
            )
            self._attr_available = True
            self._attr_native_value = 0.0
    
    async def async_reset(self) -> None:
        """Reset not applicable for instantaneous sensor."""
        _LOGGER.info("Reset not applicable for instantaneous cost remainder sensor '%s'", self._group_name)