"""Upstream sensor implementations for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .base import PhantomBaseSensor
from ..state_migration import get_migrated_state
from ..tariff import TariffManager
from ..repairs import (
    async_create_upstream_unavailable_issue,
    async_delete_upstream_unavailable_issue,
)

_LOGGER = logging.getLogger(__name__)


class PhantomUpstreamPowerSensor(PhantomBaseSensor):
    """Sensor for upstream power monitoring."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:transmission-tower"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "upstream_power")
        self._upstream_entity = upstream_entity
        self._attr_name = "Upstream Power"
        self._issue_created = False
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._upstream_entity],
                self._handle_state_change,
            )
        )
        self._update_state()
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entity."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        state = self.hass.states.get(self._upstream_entity)
        
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Return 0 instead of marking unavailable
            self._attr_available = True
            self._attr_native_value = 0.0
            
            # Create repair issue if not already created
            if not self._issue_created:
                async_create_upstream_unavailable_issue(
                    self.hass,
                    self._group_name,
                    self._upstream_entity
                )
                self._issue_created = True
        else:
            self._attr_available = True
            try:
                self._attr_native_value = float(state.state)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not convert state to float: %s", state.state)
                # Return 0 instead of marking unavailable
                self._attr_available = True
                self._attr_native_value = 0.0
            else:
                # Delete repair issue if it was created and sensor is now available
                if self._issue_created:
                    async_delete_upstream_unavailable_issue(
                        self.hass,
                        self._group_name
                    )
                    self._issue_created = False


class PhantomUpstreamEnergyMeterSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor that tracks upstream energy consumption."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    _attr_icon = "mdi:transmission-tower"
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "last_value": self._last_value,
            "source_entity": self._upstream_entity,
        }
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "upstream_energy_meter")
        self._hass = hass
        self._upstream_entity = upstream_entity
        self._attr_name = "Upstream Energy Meter"
        self._last_value = None
        self._total_consumed = 0.0
        self._issue_created = False
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Check for migrated state first (from rename)
        _LOGGER.debug("Checking for migrated state for upstream energy (unique_id: %s)", self._attr_unique_id)
        migrated_state = get_migrated_state(self._hass, self._config_entry_id, self._attr_unique_id)
        
        if migrated_state:
            try:
                self._total_consumed = float(migrated_state["state"])
                self._attr_native_value = self._total_consumed
                # Restore last_value from attributes if available
                if "last_value" in migrated_state.get("attributes", {}):
                    self._last_value = float(migrated_state["attributes"]["last_value"])
                _LOGGER.info(
                    "✓ Restored migrated upstream energy: %s kWh (from old entity: %s)",
                    self._total_consumed,
                    migrated_state.get("old_entity_id", "unknown")
                )
                # Force immediate state write after migration
                self.async_write_ha_state()
            except (ValueError, TypeError) as e:
                _LOGGER.warning("Failed to restore migrated state: %s", e)
                self._total_consumed = 0.0
                self._attr_native_value = 0.0
        else:
            _LOGGER.debug("No migrated state found for upstream energy")
            # Try to restore from previous state (normal restart)
            if (last_state := await self.async_get_last_state()) is not None:
                if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    try:
                        self._total_consumed = float(last_state.state)
                        self._attr_native_value = self._total_consumed
                        _LOGGER.info(
                            "Restored upstream energy meter: %s kWh",
                            self._total_consumed
                        )
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Could not restore upstream energy state: %s",
                            last_state.state
                        )
                        self._total_consumed = 0.0
                        self._attr_native_value = 0.0
                else:
                    self._total_consumed = 0.0
                    self._attr_native_value = 0.0
            else:
                self._total_consumed = 0.0
                self._attr_native_value = 0.0
        
        # Get initial state
        state = self.hass.states.get(self._upstream_entity)
        _LOGGER.info(
            "Initializing upstream energy meter for %s - entity: %s, state: %s",
            self._group_name,
            self._upstream_entity,
            state.state if state else "None"
        )
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._last_value = float(state.state)
                unit = state.attributes.get("unit_of_measurement")
                _LOGGER.info(
                    "Initial upstream value: %s %s",
                    self._last_value,
                    unit
                )
                # Convert Wh to kWh if needed
                if unit == UnitOfEnergy.WATT_HOUR:
                    self._last_value = self._last_value / 1000
                    _LOGGER.info("Converted initial value to kWh: %s", self._last_value)
            except (ValueError, TypeError) as err:
                _LOGGER.error("Failed to get initial upstream value: %s", err)
                self._last_value = None
        
        # Also try to restore the last tracked value from attributes
        if last_state and "last_value" in last_state.attributes:
            try:
                self._last_value = float(last_state.attributes["last_value"])
                _LOGGER.debug(
                    "Restored last tracked value for upstream: %s",
                    self._last_value
                )
            except (ValueError, TypeError):
                pass
        
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._upstream_entity],
                self._handle_state_change,
            )
        )
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entity."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        _LOGGER.debug(
            "Upstream energy state change for %s: old=%s, new=%s",
            self._upstream_entity,
            old_state.state if old_state else "None",
            new_state.state if new_state else "None"
        )
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Keep available and maintain the total
            self._attr_available = True
            # Don't update native_value, keep the accumulated total
            
            # Create repair issue if not already created
            if not self._issue_created:
                async_create_upstream_unavailable_issue(
                    self.hass,
                    self._group_name,
                    self._upstream_entity
                )
                self._issue_created = True
            
            self.async_write_ha_state()
            return
        
        try:
            # Get the new value
            new_value = float(new_state.state)
            unit = new_state.attributes.get("unit_of_measurement")
            
            _LOGGER.debug(
                "Upstream energy raw value: %s %s (last_value=%s, total_consumed=%s)",
                new_value,
                unit,
                self._last_value,
                self._total_consumed
            )
            
            # Convert Wh to kWh if needed
            if unit == UnitOfEnergy.WATT_HOUR:
                new_value = new_value / 1000
                _LOGGER.debug("Converted Wh to kWh: %s", new_value)
            
            # Calculate consumption
            if self._last_value is not None and new_value >= self._last_value:
                # Normal increase
                consumption = new_value - self._last_value
                self._total_consumed += consumption
                _LOGGER.debug(
                    "Normal consumption increase: %s kWh (total now: %s kWh)",
                    consumption,
                    self._total_consumed
                )
            elif self._last_value is not None and new_value < self._last_value:
                # Meter reset or rollover - just use the new value as consumption
                self._total_consumed += new_value
                _LOGGER.debug(
                    "Meter reset detected, adding new value: %s kWh (total now: %s kWh)",
                    new_value,
                    self._total_consumed
                )
            else:
                _LOGGER.debug(
                    "No consumption added - last_value is None or same value"
                )
            
            self._last_value = new_value
            self._attr_available = True
            self._attr_native_value = self._total_consumed
            
            # Delete repair issue if it was created and sensor is now available
            if self._issue_created:
                async_delete_upstream_unavailable_issue(
                    self.hass,
                    self._group_name
                )
                self._issue_created = False
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not update upstream meter: %s", err)
            # Keep available and maintain the total
            self._attr_available = True
            # Don't update native_value, keep the accumulated total
            
            # Create repair issue if not already created
            if not self._issue_created:
                async_create_upstream_unavailable_issue(
                    self.hass,
                    self._group_name,
                    self._upstream_entity
                )
                self._issue_created = True
        
        self.async_write_ha_state()
    
    async def async_reset(self) -> None:
        """Reset the upstream energy meter."""
        _LOGGER.info("Resetting upstream energy meter for group '%s'", self._group_name)
        self._total_consumed = 0.0
        self._attr_native_value = 0.0
        self._last_value = None
        
        # Get current value of source entity to use as new baseline
        state = self.hass.states.get(self._upstream_entity)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._last_value = float(state.state)
                # Convert Wh to kWh if needed
                if state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                    self._last_value = self._last_value / 1000
            except (ValueError, TypeError):
                _LOGGER.warning("Could not get current value for reset baseline")
        
        self.async_write_ha_state()


class PhantomUpstreamCostSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor for upstream total cost."""
    
    _attr_device_class = None
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:transmission-tower"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_meter_entity: str,
        tariff_manager: TariffManager,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "upstream_cost")
        self.hass = hass
        self._upstream_meter_entity = upstream_meter_entity
        self._tariff_manager = tariff_manager
        self._attr_name = "Upstream Cost"
        self._attr_native_unit_of_measurement = tariff_manager.currency
        self._currency_symbol = tariff_manager.currency_symbol
        self._last_energy_value = None
        self._total_cost = 0.0
        self._issue_created = False
        
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "currency_symbol": self._currency_symbol,
            "current_rate": self._tariff_manager.get_current_rate(),
            "current_period": self._tariff_manager.get_current_period(),
            "source_entity": self._upstream_meter_entity,
        }
        if self._last_energy_value is not None:
            attrs["total_energy_kwh"] = self._last_energy_value
        return attrs
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._total_cost = float(last_state.state)
                    self._attr_native_value = self._total_cost
                    self._attr_available = True
                    
                    # Restore last energy value from attributes
                    if "total_energy_kwh" in last_state.attributes:
                        self._last_energy_value = float(last_state.attributes["total_energy_kwh"])
                    
                    _LOGGER.info(
                        "Restored upstream cost: %s %s (energy: %s kWh)",
                        self._total_cost,
                        self._currency_symbol,
                        self._last_energy_value
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore upstream cost state: %s",
                        last_state.state
                    )
        
        # Track upstream meter entity
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._upstream_meter_entity],
                self._handle_state_change,
            )
        )
        
        # Initial update
        self._update_state()
    
    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state changes of tracked entity."""
        # Only update if the new state is valid
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if new_state is not None:
            self._update_state(old_state, new_state)
            self.async_write_ha_state()
    
    @callback
    def _update_state(self, old_state=None, new_state=None) -> None:
        """Update the sensor state."""
        # Get current state if not provided
        if new_state is None:
            new_state = self.hass.states.get(self._upstream_meter_entity)
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Keep sensor available but don't update value
            _LOGGER.debug(
                "Upstream cost '%s' - upstream meter unavailable",
                self._group_name,
            )
            
            # Create repair issue if not already created
            if not self._issue_created:
                async_create_upstream_unavailable_issue(
                    self.hass,
                    "upstream_cost",
                    "Upstream Energy Meter",
                    self._group_name,
                    self._upstream_meter_entity
                )
                self._issue_created = True
            return
        else:
            # Delete repair issue if it was created
            if self._issue_created:
                async_delete_upstream_unavailable_issue(
                    self.hass,
                    "upstream_cost",
                    "Upstream Energy Meter",
                    self._group_name
                )
                self._issue_created = False
        
        try:
            current_energy = float(new_state.state)
            
            # Calculate cost increase if we have a previous value
            if self._last_energy_value is not None and current_energy >= self._last_energy_value:
                # Normal increase
                energy_consumed = current_energy - self._last_energy_value
                
                if energy_consumed > 0:
                    # Get current tariff rate
                    current_rate = self._tariff_manager.get_current_rate()
                    
                    # Calculate cost for this consumption
                    cost_increase = self._tariff_manager.calculate_energy_cost(
                        energy_consumed, 
                        current_rate
                    )
                    
                    self._total_cost += cost_increase
                    
                    _LOGGER.debug(
                        "Upstream cost '%s' - consumed %.3f kWh @ %.3f %s/kWh = %.2f %s (total: %.2f %s)",
                        self._group_name,
                        energy_consumed,
                        current_rate,
                        self._currency_symbol,
                        cost_increase,
                        self._currency_symbol,
                        self._total_cost,
                        self._currency_symbol,
                    )
            elif self._last_energy_value is not None and current_energy < self._last_energy_value:
                # Meter reset detected - use the new value as consumption
                current_rate = self._tariff_manager.get_current_rate()
                cost_increase = self._tariff_manager.calculate_energy_cost(
                    current_energy, 
                    current_rate
                )
                self._total_cost += cost_increase
                
                _LOGGER.debug(
                    "Upstream cost '%s' - meter reset detected, adding %.3f kWh @ %.3f %s/kWh = %.2f %s",
                    self._group_name,
                    current_energy,
                    current_rate,
                    self._currency_symbol,
                    cost_increase,
                    self._currency_symbol,
                )
            
            self._last_energy_value = current_energy
            self._attr_native_value = self._total_cost
            self._attr_available = True
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning(
                "Error calculating upstream cost for '%s': %s (state: %s)",
                self._group_name,
                err,
                new_state.state,
            )
    
    async def async_reset(self) -> None:
        """Reset the upstream cost sensor."""
        _LOGGER.info("Resetting upstream cost for group '%s'", self._group_name)
        self._total_cost = 0.0
        self._attr_native_value = 0.0
        self._last_energy_value = None
        
        # Get current value of upstream meter to use as new baseline
        state = self.hass.states.get(self._upstream_meter_entity)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._last_energy_value = float(state.state)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not get current energy value for reset baseline")
        
        self.async_write_ha_state()