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
    """Sensor for accumulated cost remainder (unaccounted cost over time)."""
    
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
        self._last_upstream_value = None
        self._last_total_value = None
        self._accumulated_remainder = 0.0
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "currency_symbol": self._currency_symbol,
            "upstream_cost_entity": self._upstream_cost_entity,
            "group_total_cost_entity": self._group_total_cost_entity,
            "accumulated_remainder": self._accumulated_remainder,
        }
        
        # Show instantaneous remainder for reference
        if self._last_upstream_value is not None and self._last_total_value is not None:
            attrs["instantaneous_remainder"] = self._last_upstream_value - self._last_total_value
            attrs["instantaneous_remainder_percent"] = (
                ((self._last_upstream_value - self._last_total_value) / self._last_upstream_value * 100)
                if self._last_upstream_value > 0 else 0
            )
        if self._last_upstream_value is not None:
            attrs["last_upstream_value"] = self._last_upstream_value
        if self._last_total_value is not None:
            attrs["last_total_value"] = self._last_total_value
                
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
                    
                    # Try to restore tracking values if they exist
                    if "last_upstream_value" in last_state.attributes:
                        self._last_upstream_value = float(last_state.attributes["last_upstream_value"])
                    if "last_total_value" in last_state.attributes:
                        self._last_total_value = float(last_state.attributes["last_total_value"])
                    
                    _LOGGER.info(
                        "Restored cost remainder for '%s': %.6f %s (upstream: %s, total: %s)",
                        self._group_name,
                        self._accumulated_remainder,
                        self._currency_symbol,
                        self._last_upstream_value,
                        self._last_total_value,
                    )
                except (ValueError, TypeError) as e:
                    _LOGGER.warning(
                        "Failed to restore cost remainder state: %s",
                        e,
                    )
                    self._accumulated_remainder = 0.0
                    self._attr_native_value = 0.0
        else:
            self._accumulated_remainder = 0.0
            self._attr_native_value = 0.0
            _LOGGER.info(
                "No previous state for cost remainder '%s', starting fresh",
                self._group_name,
            )
        
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
            # Don't update if upstream is not available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = self._accumulated_remainder
            return
            
        # Get group total cost
        total_state = self.hass.states.get(self._group_total_cost_entity)
        if total_state is None or total_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(
                "Cost remainder '%s' - group total cost entity %s is unavailable",
                self._group_name,
                self._group_total_cost_entity,
            )
            # Don't update if total is not available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = self._accumulated_remainder
            return
        
        try:
            upstream_cost = float(upstream_state.state)
            total_cost = float(total_state.state)
            
            # Log current values for debugging
            _LOGGER.debug(
                "Cost remainder '%s' - current values: upstream=%.6f, total=%.6f, last_upstream=%s, last_total=%s",
                self._group_name,
                upstream_cost,
                total_cost,
                self._last_upstream_value,
                self._last_total_value,
            )
            
            # Calculate deltas if we have previous values
            if self._last_upstream_value is not None and self._last_total_value is not None:
                upstream_delta = upstream_cost - self._last_upstream_value
                total_delta = total_cost - self._last_total_value
                
                # Only process if there's actual cost increase
                if upstream_delta > 0.000001 or total_delta > 0.000001:
                    # Calculate the remainder delta
                    remainder_delta = upstream_delta - total_delta
                    
                    # Only accumulate positive remainder (unaccounted cost)
                    if remainder_delta > 0.000001:  # Use small threshold to avoid floating point issues
                        self._accumulated_remainder += remainder_delta
                        _LOGGER.info(
                            "Cost remainder '%s' - upstream delta: %.6f, total delta: %.6f, remainder delta: %.6f, accumulated: %.6f %s",
                            self._group_name,
                            upstream_delta,
                            total_delta,
                            remainder_delta,
                            self._accumulated_remainder,
                            self._currency_symbol,
                        )
                    else:
                        _LOGGER.debug(
                            "Cost remainder '%s' - devices caught up, not accumulating negative remainder: %.6f %s",
                            self._group_name,
                            remainder_delta,
                            self._currency_symbol,
                        )
                elif upstream_delta < -0.000001 or total_delta < -0.000001:
                    # Handle meter resets - just log it, don't accumulate negative deltas
                    _LOGGER.info(
                        "Cost remainder '%s' - meter reset detected (upstream: %.6f->%.6f, total: %.6f->%.6f)",
                        self._group_name,
                        self._last_upstream_value,
                        upstream_cost,
                        self._last_total_value,
                        total_cost,
                    )
            else:
                # First run - just set the tracking values
                _LOGGER.info(
                    "Cost remainder '%s' - initializing with upstream=%.6f, total=%.6f",
                    self._group_name,
                    upstream_cost,
                    total_cost,
                )
            
            # Update tracking values
            self._last_upstream_value = upstream_cost
            self._last_total_value = total_cost
            
            # Sanity check: accumulated remainder should not exceed instantaneous remainder
            instantaneous_remainder = upstream_cost - total_cost
            if instantaneous_remainder > 0 and self._accumulated_remainder > instantaneous_remainder:
                _LOGGER.warning(
                    "Cost remainder '%s' - accumulated remainder (%.6f) exceeds instantaneous remainder (%.6f), resetting to instantaneous value",
                    self._group_name,
                    self._accumulated_remainder,
                    instantaneous_remainder,
                )
                self._accumulated_remainder = instantaneous_remainder
            
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
            self._attr_available = True
            self._attr_native_value = self._accumulated_remainder
    
    async def async_reset(self) -> None:
        """Reset the cost remainder accumulator."""
        _LOGGER.info("Resetting cost remainder for group '%s'", self._group_name)
        self._accumulated_remainder = 0.0
        self._attr_native_value = 0.0
        # Reset tracking values to force recalculation
        self._last_upstream_value = None
        self._last_total_value = None
        # Get current values and initialize tracking
        self._update_state()
        self.async_write_ha_state()