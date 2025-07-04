"""Cost tracking sensor implementations for Phantom Power Monitoring."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er

from .base import PhantomBaseSensor, PhantomDeviceSensor
from ..const import CONF_DEVICE_ID, DOMAIN
from ..tariff import TariffManager
from ..tariff_external import ExternalTariffManager

_LOGGER = logging.getLogger(__name__)

# Force update interval to ensure graphs stay smooth and responsive
COST_SENSOR_UPDATE_INTERVAL = timedelta(seconds=10)


class PhantomDeviceHourlyCostSensor(PhantomDeviceSensor):
    """Sensor for device hourly cost rate."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:currency-usd"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        device_name: str,
        device_id: str,
        power_entity: str,
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, device_name, device_id, "hourly_cost")
        self.hass = hass
        self._power_entity = power_entity
        self._tariff_manager = tariff_manager
        self._attr_name = f"{device_name} Hourly Cost"
        self._attr_native_unit_of_measurement = f"{tariff_manager.currency_symbol}/h"
        self._current_power = 0.0
        self._current_rate = 0.0
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "current_rate": f"{self._current_rate:.3f} {self._tariff_manager.currency_symbol}/kWh",
            "current_period": self._tariff_manager.get_current_period(),
            "power_watts": self._current_power,
            "currency": self._tariff_manager.currency,
        }
        # Add external sensor info if using external tariff manager
        if isinstance(self._tariff_manager, ExternalTariffManager):
            if self._tariff_manager._rate_entity:
                attrs["rate_source"] = self._tariff_manager._rate_entity
            if self._tariff_manager._period_entity:
                attrs["period_source"] = self._tariff_manager._period_entity
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._power_entity],
                self._handle_state_change,
            )
        )
        # Update every minute to catch rate changes
        self._update_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_time_update,
                timedelta(seconds=30)
            )
        )
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entity."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _handle_time_update(self, now) -> None:
        """Handle time updates for rate changes."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        # Get current power
        state = self.hass.states.get(self._power_entity)
        
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
            self._attr_native_value = None
            return
            
        try:
            self._current_power = float(state.state)
        except (ValueError, TypeError):
            self._attr_available = False
            self._attr_native_value = None
            return
        
        # Get current rate
        self._current_rate = self._tariff_manager.get_current_rate()
        
        # Calculate cost per hour
        cost_per_hour = self._tariff_manager.calculate_cost_per_hour(self._current_power)
        
        self._attr_available = True
        self._attr_native_value = cost_per_hour


class PhantomGroupHourlyCostSensor(PhantomBaseSensor):
    """Sensor for group hourly cost rate."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:currency-usd"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        power_entities: list[str],
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "hourly_cost")
        self.hass = hass
        self._power_entities = power_entities
        self._tariff_manager = tariff_manager
        self._attr_name = "Hourly Cost"
        self._attr_native_unit_of_measurement = f"{tariff_manager.currency_symbol}/h"
        self._total_power = 0.0
        self._current_rate = 0.0
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "current_rate": f"{self._current_rate:.3f} {self._tariff_manager.currency_symbol}/kWh",
            "current_period": self._tariff_manager.get_current_period(),
            "total_power_watts": self._total_power,
            "currency": self._tariff_manager.currency,
        }
        # Add external sensor info if using external tariff manager
        if isinstance(self._tariff_manager, ExternalTariffManager):
            if self._tariff_manager._rate_entity:
                attrs["rate_source"] = self._tariff_manager._rate_entity
            if self._tariff_manager._period_entity:
                attrs["period_source"] = self._tariff_manager._period_entity
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._power_entities,
                self._handle_state_change,
            )
        )
        # Update every minute to catch rate changes
        self._update_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_time_update,
                timedelta(seconds=30)
            )
        )
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entities."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _handle_time_update(self, now) -> None:
        """Handle time updates for rate changes."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        # Calculate total power
        total = 0
        all_unavailable = True
        
        for entity_id in self._power_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
                
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                all_unavailable = False
                try:
                    total += float(state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert state to float: %s", state.state)
        
        if all_unavailable:
            self._attr_available = False
            self._attr_native_value = None
            return
        
        self._total_power = total
        
        # Get current rate
        self._current_rate = self._tariff_manager.get_current_rate()
        
        # Calculate cost per hour
        cost_per_hour = self._tariff_manager.calculate_cost_per_hour(self._total_power)
        
        self._attr_available = True
        self._attr_native_value = cost_per_hour


class PhantomTouRateSensor(PhantomBaseSensor):
    """Sensor showing current TOU rate."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3
    _attr_icon = "mdi:cash-multiple"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "current_rate")
        self._tariff_manager = tariff_manager
        self._attr_name = "Current Electricity Rate"
        self._attr_native_unit_of_measurement = f"{tariff_manager.currency_symbol}/kWh"
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "current_period": self._tariff_manager.get_current_period(),
            "currency": self._tariff_manager.currency,
        }
        # Add external sensor info if using external tariff manager
        if isinstance(self._tariff_manager, ExternalTariffManager):
            if self._tariff_manager._rate_entity:
                attrs["rate_source"] = self._tariff_manager._rate_entity
            if self._tariff_manager._period_entity:
                attrs["period_source"] = self._tariff_manager._period_entity
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Update every minute to catch rate changes
        self._update_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_time_update,
                timedelta(seconds=30)
            )
        )
    
    @callback
    def _handle_time_update(self, now) -> None:
        """Handle time updates for rate changes."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        self._attr_native_value = self._tariff_manager.get_current_rate()
        self._attr_available = True


class PhantomDeviceTotalCostSensor(PhantomDeviceSensor, RestoreEntity):
    """Sensor that tracks total energy cost for a device."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        device_name: str,
        device_id: str,
        utility_meter_entity: str,
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, device_name, device_id, "total_cost")
        self.hass = hass
        self._utility_meter_entity = utility_meter_entity
        self._tariff_manager = tariff_manager
        self._attr_name = f"{device_name} Total Cost"
        self._attr_native_unit_of_measurement = tariff_manager.currency
        self._last_meter_value = None
        self._total_cost = 0.0
        self._last_rate = None
        self._last_update_time = None
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "currency_symbol": self._tariff_manager.currency_symbol,
            "source_entity": self._utility_meter_entity,
            "last_meter_value": self._last_meter_value,
            "tariff_enabled": self._tariff_manager.enabled,
            "current_rate": self._tariff_manager.get_current_rate() if self._tariff_manager.enabled else None,
        }
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        _LOGGER.info(
            "Total cost sensor '%s' added to hass, tracking utility meter: %s, tariff enabled: %s",
            self._device_name,
            self._utility_meter_entity,
            self._tariff_manager.enabled
        )
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._total_cost = float(last_state.state)
                    self._attr_native_value = self._total_cost
                    # Restore last meter value from attributes
                    if "last_meter_value" in last_state.attributes:
                        self._last_meter_value = float(last_state.attributes["last_meter_value"])
                    elif "last_energy_value" in last_state.attributes:  # Backwards compatibility
                        self._last_meter_value = float(last_state.attributes["last_energy_value"])
                    _LOGGER.info(
                        "Restored total cost for %s: %s %s",
                        self._device_name,
                        self._total_cost,
                        self._tariff_manager.currency
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore state for %s: %s",
                        self._device_name,
                        last_state.state
                    )
                    self._total_cost = 0.0
                    self._attr_native_value = 0.0
            else:
                self._total_cost = 0.0
                self._attr_native_value = 0.0
        else:
            self._total_cost = 0.0
            self._attr_native_value = 0.0
        
        # Get initial meter value
        state = self.hass.states.get(self._utility_meter_entity)
        if state is None:
            _LOGGER.warning(
                "Utility meter entity %s not found for device %s",
                self._utility_meter_entity,
                self._device_name
            )
            self._attr_available = False
        elif state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.warning(
                "Utility meter entity %s is %s for device %s",
                self._utility_meter_entity,
                state.state,
                self._device_name
            )
            self._attr_available = False
        else:
            try:
                # Utility meter is already in kWh
                self._last_meter_value = float(state.state)
                _LOGGER.info(
                    "Initial meter value for %s: %s kWh (entity: %s)",
                    self._device_name,
                    self._last_meter_value,
                    self._utility_meter_entity
                )
                self._attr_available = True
                # Initialize tracking variables
                self._last_rate = self._tariff_manager.get_current_rate()
                self._last_update_time = datetime.now()
            except (ValueError, TypeError) as err:
                _LOGGER.error(
                    "Error parsing initial meter value for %s: %s (value: %s)",
                    self._device_name,
                    err,
                    state.state
                )
                self._attr_available = False
        
        # Only track if we have a valid entity
        if state is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._utility_meter_entity],
                    self._handle_state_change,
                )
            )
            _LOGGER.info(
                "Started tracking utility meter %s for device %s",
                self._utility_meter_entity,
                self._device_name
            )
            
            # Add periodic updates to ensure smooth graphs
            self.async_on_remove(
                async_track_time_interval(
                    self.hass,
                    self._periodic_update,
                    COST_SENSOR_UPDATE_INTERVAL
                )
            )
            _LOGGER.debug(
                "Added %s second periodic update for %s total cost sensor",
                COST_SENSOR_UPDATE_INTERVAL.total_seconds(),
                self._device_name
            )
        else:
            _LOGGER.error(
                "Cannot track utility meter %s for device %s - entity not found",
                self._utility_meter_entity,
                self._device_name
            )
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entity."""
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
            # Utility meter value is already in kWh
            new_meter_value = float(new_state.state)
            
            _LOGGER.debug(
                "Total cost sensor %s processing meter value: %.3f kWh (previous: %s)",
                self._device_name,
                new_meter_value,
                self._last_meter_value if self._last_meter_value is not None else "None"
            )
            
            if self._last_meter_value is not None:
                # Calculate difference with higher precision
                meter_diff = new_meter_value - self._last_meter_value
                
                if meter_diff > 0.000001:  # Very small positive change threshold
                    # Calculate energy consumed since last update
                    energy_delta = meter_diff
                    
                    # Get current rate and calculate cost
                    current_rate = self._tariff_manager.get_current_rate()
                    cost_delta = self._tariff_manager.calculate_energy_cost(energy_delta, current_rate)
                    
                    # Add to total cost with full precision
                    self._total_cost += cost_delta
                    self._attr_native_value = self._total_cost
                    
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
                    
                    # Update tracking for rate changes
                    self._last_rate = current_rate
                    self._last_update_time = datetime.now()
                elif meter_diff < -0.000001:  # Negative change (meter reset)
                    # Meter was reset
                    _LOGGER.info(
                        "Meter reset detected for %s: %.6f -> %.6f kWh",
                        self._device_name,
                        self._last_meter_value,
                        new_meter_value
                    )
                    # Don't change the total cost on meter reset
                else:
                    # Very small or no change, but still update native value
                    # This ensures the sensor appears "alive" in the UI
                    self._attr_native_value = self._total_cost
                    _LOGGER.debug(
                        "Minimal change for %s: meter diff %.9f kWh, total cost remains %.3f",
                        self._device_name,
                        meter_diff,
                        self._total_cost
                    )
            else:
                # First reading, just store the value
                _LOGGER.info(
                    "First meter reading for %s: %.3f kWh, initializing cost tracking",
                    self._device_name,
                    new_meter_value
                )
            
            self._last_meter_value = new_meter_value
            self._attr_available = True
            # Ensure native value is set to current total cost
            self._attr_native_value = self._total_cost
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Error calculating cost for %s: %s", self._device_name, err)
            self._attr_available = False
        
        # Always write state after processing
        self.async_write_ha_state()
    
    @callback
    def _periodic_update(self, now) -> None:
        """Force periodic update to keep graphs smooth and responsive."""
        # Only update if we have valid data
        if self._attr_available and self._attr_native_value is not None:
            current_rate = self._tariff_manager.get_current_rate()
            
            # Check if we need to handle a rate change during constant power consumption
            if (self._last_rate is not None and 
                self._last_update_time is not None and
                current_rate != self._last_rate and
                self._last_meter_value is not None):
                
                # Get current meter value to check if there's ongoing consumption
                meter_state = self.hass.states.get(self._utility_meter_entity)
                if meter_state and meter_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    try:
                        current_meter_value = float(meter_state.state)
                        
                        # If meter hasn't changed, we need to estimate consumption based on time
                        # This handles the case where power is constant during a rate change
                        if abs(current_meter_value - self._last_meter_value) < 0.000001:
                            # Calculate time-based estimation if we have a power entity
                            power_entity_id = self._utility_meter_entity.replace("_energy_daily", "")
                            power_state = self.hass.states.get(power_entity_id)
                            
                            if power_state and power_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                                try:
                                    power_watts = float(power_state.state)
                                    if power_watts > 0:
                                        # Calculate energy consumed since last update
                                        time_diff = (now - self._last_update_time).total_seconds() / 3600  # hours
                                        estimated_energy = (power_watts / 1000) * time_diff  # kWh
                                        
                                        # Calculate cost at the old rate for the period
                                        cost_at_old_rate = self._tariff_manager.calculate_energy_cost(
                                            estimated_energy, self._last_rate
                                        )
                                        
                                        # Add the cost
                                        self._total_cost += cost_at_old_rate
                                        self._attr_native_value = self._total_cost
                                        
                                        _LOGGER.info(
                                            "Applied TOU rate change for %s: %.3f kWh at old rate %.3f %s/kWh = %.6f %s",
                                            self._device_name,
                                            estimated_energy,
                                            self._last_rate,
                                            self._tariff_manager.currency_symbol,
                                            cost_at_old_rate,
                                            self._tariff_manager.currency
                                        )
                                except (ValueError, TypeError):
                                    pass
                    except (ValueError, TypeError):
                        pass
            
            # Update tracking variables
            self._last_rate = current_rate
            self._last_update_time = now
            
            _LOGGER.debug(
                "Periodic update for %s total cost sensor: %.3f %s (rate: %.3f)",
                self._device_name,
                self._attr_native_value,
                self._tariff_manager.currency,
                current_rate
            )
            # Force state write to ensure UI updates
            self.async_write_ha_state()
    
    async def async_reset(self) -> None:
        """Reset the total cost."""
        _LOGGER.info("Resetting total cost for device '%s'", self._device_name)
        self._total_cost = 0.0
        self._attr_native_value = 0.0
        
        # Keep current meter value as baseline for next calculation
        state = self.hass.states.get(self._utility_meter_entity)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._last_meter_value = float(state.state)
            except (ValueError, TypeError):
                pass
        
        self.async_write_ha_state()


class PhantomGroupTotalCostSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor that tracks total energy cost for a group."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:cash-multiple"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        devices: list[dict[str, Any]],
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "total_cost")
        self.hass = hass
        self._devices = devices
        self._tariff_manager = tariff_manager
        self._attr_name = "Total Cost"
        self._attr_native_unit_of_measurement = tariff_manager.currency
        self._device_cost_entities = []
        self._setup_delayed = False
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "currency_symbol": self._tariff_manager.currency_symbol,
            "device_count": len(self._device_cost_entities),
        }
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Delay setup to allow device cost sensors to be created
        self.hass.async_create_task(self._delayed_setup())
    
    async def _delayed_setup(self) -> None:
        """Set up tracking after a delay."""
        await asyncio.sleep(2)
        
        # Find device total cost entities
        self._device_cost_entities = await self._find_device_cost_entities()
        _LOGGER.debug(
            "Group total cost for '%s' - found %d device cost entities",
            self._group_name,
            len(self._device_cost_entities),
        )
        
        if self._device_cost_entities:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._device_cost_entities,
                    self._handle_state_change,
                )
            )
        
        self._setup_delayed = True
        self._update_state()
        self.async_write_ha_state()
    
    async def _find_device_cost_entities(self) -> list[str]:
        """Find device total cost entities."""
        entity_registry = er.async_get(self.hass)
        cost_entities = []
        
        for device in self._devices:
            device_id = device.get(CONF_DEVICE_ID)
            
            if device_id:
                expected_unique_id = f"{device_id}_total_cost"
                
                # Find entity with this unique ID
                for entity_id, entry in entity_registry.entities.items():
                    if (
                        entry.unique_id == expected_unique_id
                        and entry.domain == "sensor"
                        and entry.platform == DOMAIN
                    ):
                        cost_entities.append(entity_id)
                        break
        
        return cost_entities
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entities."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        if not self._setup_delayed:
            return
        
        # Sum all device costs
        total = 0
        any_available = False
        
        for entity_id in self._device_cost_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
                
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                any_available = True
                try:
                    total += float(state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert state to float: %s", state.state)
        
        if not any_available:
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True
            self._attr_native_value = total
    
    async def async_reset(self) -> None:
        """Reset the group total cost.
        
        Note: This doesn't actually reset device costs. The group total is just
        a sum of device costs, so when device costs are reset individually,
        the group total will automatically update to reflect the new sum.
        """
        _LOGGER.info("Group total cost sensor '%s' reset requested", self._group_name)
        _LOGGER.info(
            "Group total cost is the sum of %d device cost sensors. "
            "Reset individual device costs to reset the group total.",
            len(self._device_cost_entities)
        )
        
        # Force an immediate update to reflect any recent device resets
        self._update_state()
        self.async_write_ha_state()