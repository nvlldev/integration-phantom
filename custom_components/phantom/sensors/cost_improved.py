"""Improved cost sensor with better update handling."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .cost import PhantomDeviceTotalCostSensor as OriginalTotalCostSensor

_LOGGER = logging.getLogger(__name__)

# Force update interval to ensure graphs update smoothly
FORCE_UPDATE_INTERVAL = timedelta(minutes=1)


class PhantomDeviceTotalCostSensorImproved(OriginalTotalCostSensor):
    """Improved total cost sensor with periodic updates."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the improved sensor."""
        super().__init__(*args, **kwargs)
        self._last_update_value = None
        self._force_update_unsub = None
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Add periodic update to ensure smooth graphs
        self._force_update_unsub = async_track_time_interval(
            self.hass,
            self._force_update,
            FORCE_UPDATE_INTERVAL
        )
        self.async_on_remove(self._force_update_unsub)
        
        _LOGGER.info(
            "Enhanced total cost sensor '%s' with %s minute update interval",
            self._device_name,
            FORCE_UPDATE_INTERVAL.total_seconds() / 60
        )
    
    @callback
    def _force_update(self, now) -> None:
        """Force update even if value hasn't changed."""
        # Only force update if we have valid data
        if self._attr_available and self._attr_native_value is not None:
            # Check if value actually changed since last forced update
            if self._last_update_value != self._attr_native_value:
                _LOGGER.debug(
                    "Force updating %s cost sensor: %.3f -> %.3f",
                    self._device_name,
                    self._last_update_value or 0,
                    self._attr_native_value
                )
                self._last_update_value = self._attr_native_value
                self.async_write_ha_state()
            else:
                # Even if value hasn't changed, update state to keep graphs smooth
                # This helps with long periods of no consumption
                self.async_write_ha_state()
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes with improved precision."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        _LOGGER.debug(
            "Total cost sensor %s received state change: %s -> %s",
            self._device_name,
            old_state.state if old_state else "None",
            new_state.state if new_state else "None"
        )
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(
                "Total cost sensor %s marking unavailable due to state: %s",
                self._device_name,
                new_state.state if new_state else "None"
            )
            self._attr_available = False
            return
        
        try:
            # Use higher precision internally
            new_meter_value = float(new_state.state)
            
            _LOGGER.debug(
                "Total cost sensor %s processing meter value: %.6f kWh (previous: %s)",
                self._device_name,
                new_meter_value,
                f"{self._last_meter_value:.6f}" if self._last_meter_value is not None else "None"
            )
            
            if self._last_meter_value is not None:
                # Use higher precision for comparison
                meter_diff = new_meter_value - self._last_meter_value
                
                if meter_diff > 0.000001:  # More sensitive threshold
                    # Calculate energy consumed since last update
                    energy_delta = meter_diff
                    
                    # Get current rate and calculate cost
                    current_rate = self._tariff_manager.get_current_rate()
                    cost_delta = self._tariff_manager.calculate_energy_cost(energy_delta, current_rate)
                    
                    # Add to total cost with full precision
                    self._total_cost += cost_delta
                    
                    # Round only for display
                    self._attr_native_value = round(self._total_cost, 3)
                    
                    _LOGGER.info(
                        "Device %s consumed %.6f kWh at rate %.3f %s/kWh, cost delta: %.6f, total: %.3f %s",
                        self._device_name,
                        energy_delta,
                        current_rate,
                        self._tariff_manager.currency_symbol,
                        cost_delta,
                        self._total_cost,
                        self._tariff_manager.currency
                    )
                elif meter_diff < -0.000001:  # More sensitive threshold
                    # Meter was reset
                    _LOGGER.info(
                        "Meter reset detected for %s: %.6f -> %.6f",
                        self._device_name,
                        self._last_meter_value,
                        new_meter_value
                    )
                else:
                    # Very small change, but we should still update the display
                    # to keep graphs smooth
                    _LOGGER.debug(
                        "Minimal consumption change for %s: meter change of %.6f kWh",
                        self._device_name,
                        meter_diff
                    )
            else:
                # First reading, just store the value
                _LOGGER.info(
                    "First meter reading for %s: %.6f kWh, initializing cost tracking",
                    self._device_name,
                    new_meter_value
                )
            
            self._last_meter_value = new_meter_value
            self._attr_available = True
            # Ensure native value is set to current total cost
            self._attr_native_value = round(self._total_cost, 3)
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Error calculating cost for %s: %s", self._device_name, err)
            self._attr_available = False
        
        # Always write state after processing
        self.async_write_ha_state()


class PhantomGroupTotalCostSensorImproved(PhantomGroupTotalCostSensor):
    """Improved group total cost sensor with periodic updates."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the improved sensor."""
        super().__init__(*args, **kwargs)
        self._force_update_unsub = None
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Add periodic update after delayed setup completes
        async def setup_periodic_update():
            await asyncio.sleep(5)  # Wait for delayed setup
            if self._setup_delayed:
                self._force_update_unsub = async_track_time_interval(
                    self.hass,
                    self._force_update,
                    FORCE_UPDATE_INTERVAL
                )
                self.async_on_remove(self._force_update_unsub)
                _LOGGER.info(
                    "Enhanced group total cost sensor '%s' with %s minute update interval",
                    self._group_name,
                    FORCE_UPDATE_INTERVAL.total_seconds() / 60
                )
        
        self.hass.async_create_task(setup_periodic_update())
    
    @callback
    def _force_update(self, now) -> None:
        """Force update to keep graphs smooth."""
        if self._setup_delayed:
            self._update_state()
            self.async_write_ha_state()