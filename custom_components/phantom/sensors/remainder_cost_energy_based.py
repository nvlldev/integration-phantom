"""Energy-based cost remainder sensor implementation for Phantom Power Monitoring."""
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


class PhantomEnergyBasedCostRemainderSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor for cost of energy remainder."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-minus"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        energy_remainder_entity: str | None,
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the cost remainder sensor."""
        super().__init__(config_entry_id, group_name, group_id, "cost_remainder")
        self.hass = hass
        self._energy_remainder_entity = energy_remainder_entity
        self._tariff_manager = tariff_manager
        self._attr_name = "Cost Remainder"
        self._attr_native_unit_of_measurement = tariff_manager.currency
        self._currency_symbol = tariff_manager.currency_symbol
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "currency_symbol": self._currency_symbol,
            "current_rate": self._tariff_manager.get_current_rate(),
        }
        if self._energy_remainder_entity:
            attrs["energy_remainder_entity"] = self._energy_remainder_entity
            
            # Get energy remainder value for additional context
            energy_state = self.hass.states.get(self._energy_remainder_entity)
            if energy_state and energy_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    energy_value = float(energy_state.state)
                    attrs["energy_remainder_kwh"] = energy_value
                except (ValueError, TypeError):
                    pass
        else:
            attrs["info"] = "No energy remainder entity configured"
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
        
        # Track energy remainder entity
        if self._energy_remainder_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._energy_remainder_entity],
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
        if not self._energy_remainder_entity:
            # No energy remainder entity configured
            self._attr_available = False
            self._attr_native_value = None
            _LOGGER.debug(
                "Cost remainder '%s' unavailable - no energy remainder entity configured",
                self._group_name,
            )
            return
        
        # Get energy remainder value
        energy_state = self.hass.states.get(self._energy_remainder_entity)
        if energy_state is None or energy_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Energy remainder not available
            _LOGGER.debug(
                "Cost remainder '%s' - energy remainder entity %s is unavailable",
                self._group_name,
                self._energy_remainder_entity,
            )
            # Keep previous value during restart
            return
        
        try:
            energy_remainder_kwh = float(energy_state.state)
            
            # Get current tariff rate
            current_rate = self._tariff_manager.get_current_rate()
            
            # Calculate cost of energy remainder
            # Energy remainder can be negative (when devices use more than upstream)
            cost_remainder = self._tariff_manager.calculate_energy_cost(
                abs(energy_remainder_kwh), 
                current_rate
            )
            
            # Preserve the sign - if energy remainder is negative, cost should be negative
            if energy_remainder_kwh < 0:
                cost_remainder = -cost_remainder
            
            self._attr_native_value = cost_remainder
            self._attr_available = True
            
            _LOGGER.debug(
                "Cost remainder '%s' calculated: %.3f kWh @ %.3f %s/kWh = %.2f %s",
                self._group_name,
                energy_remainder_kwh,
                current_rate,
                self._currency_symbol,
                cost_remainder,
                self._tariff_manager.currency,
            )
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Error calculating cost remainder for '%s': %s (energy state: %s)",
                self._group_name,
                err,
                energy_state.state,
            )
            self._attr_available = False