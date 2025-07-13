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

from .base import PhantomBaseSensor
from ..tariff import TariffManager

_LOGGER = logging.getLogger(__name__)


class PhantomEnergyBasedCostRemainderSensor(PhantomBaseSensor):
    """Sensor showing instantaneous cost of energy remainder."""
    
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
            "current_period": self._tariff_manager.get_current_period(),
            "energy_remainder_entity": self._energy_remainder_entity,
        }
        
        # Get current energy remainder value for additional context
        if self._energy_remainder_entity:
            energy_state = self.hass.states.get(self._energy_remainder_entity)
            if energy_state and energy_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    energy_value = float(energy_state.state)
                    attrs["energy_remainder_kwh"] = energy_value
                    attrs["calculation"] = f"{energy_value:.3f} kWh × {self._tariff_manager.get_current_rate():.3f} {self._currency_symbol}/kWh"
                except (ValueError, TypeError):
                    pass
        
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
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
            self._attr_available = True
            self._attr_native_value = 0.0
            _LOGGER.debug(
                "Cost remainder '%s' - no energy remainder entity configured",
                self._group_name,
            )
            return
        
        # Get energy remainder value
        energy_state = self.hass.states.get(self._energy_remainder_entity)
        if energy_state is None or energy_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Energy remainder not available - show 0
            _LOGGER.debug(
                "Cost remainder '%s' - energy remainder entity %s is unavailable",
                self._group_name,
                self._energy_remainder_entity,
            )
            self._attr_available = True
            self._attr_native_value = 0.0
            return
        
        try:
            # Get current energy remainder
            energy_remainder = float(energy_state.state)
            
            # Get current tariff rate
            current_rate = self._tariff_manager.get_current_rate()
            
            # Calculate instantaneous cost
            cost_remainder = energy_remainder * current_rate
            
            self._attr_native_value = cost_remainder
            self._attr_available = True
            
            _LOGGER.debug(
                "Cost remainder '%s' = %.3f kWh × %.3f %s/kWh = %.2f %s",
                self._group_name,
                energy_remainder,
                current_rate,
                self._currency_symbol,
                cost_remainder,
                self._currency_symbol,
            )
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Error calculating cost remainder for '%s': %s (energy state: %s)",
                self._group_name,
                err,
                energy_state.state,
            )
            self._attr_available = True
            self._attr_native_value = 0.0
    
    async def async_reset(self) -> None:
        """Reset not applicable for instantaneous sensor."""
        _LOGGER.info("Reset not applicable for instantaneous cost remainder sensor '%s'", self._group_name)