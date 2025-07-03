"""Energy and utility meter sensor implementations for Phantom Power Monitoring."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er

from .base import PhantomBaseSensor, PhantomDeviceSensor
from ..const import CONF_DEVICE_ID
from ..state_migration import get_migrated_state
from ..utils import sanitize_name

_LOGGER = logging.getLogger(__name__)

# Force update interval to ensure downstream sensors stay responsive
UTILITY_METER_UPDATE_INTERVAL = timedelta(seconds=30)


class PhantomEnergySensor(PhantomBaseSensor, RestoreEntity):
    """Sensor for total energy consumption of a group."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "energy_total")
        self.hass = hass
        self._devices = devices
        self._attr_name = "Energy Total"
        self._utility_meter_entities = []
        self._setup_delayed = False
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._attr_native_value = float(last_state.state)
                except (ValueError, TypeError):
                    self._attr_native_value = 0.0
            else:
                self._attr_native_value = 0.0
        else:
            self._attr_native_value = 0.0
        
        # Delay setup to allow utility meters to be created
        self.hass.async_create_task(self._delayed_setup())
    
    async def _delayed_setup(self) -> None:
        """Set up tracking after a delay."""
        # Check if migration is active
        migration_data = self.hass.data.get("phantom_state_migration", {}).get(self._config_entry_id)
        if migration_data:
            _LOGGER.debug("Migration detected for energy total, waiting longer for utility meters to settle")
            await asyncio.sleep(3)  # Wait longer during migration
        else:
            await asyncio.sleep(2)
        
        # Find utility meter entities for this group
        self._utility_meter_entities = await self._find_utility_meter_entities()
        
        if self._utility_meter_entities:
            _LOGGER.debug(
                "Found %d utility meter entities for group '%s' energy total: %s",
                len(self._utility_meter_entities),
                self._group_name,
                self._utility_meter_entities,
            )
            
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._utility_meter_entities,
                    self._handle_state_change,
                )
            )
        else:
            _LOGGER.warning(
                "No utility meter entities found for group '%s' energy total",
                self._group_name,
            )
        
        self._setup_delayed = True
        self._update_state()
        self.async_write_ha_state()
    
    async def _find_utility_meter_entities(self) -> list[str]:
        """Find utility meter entities for this group's devices."""
        from ..const import DOMAIN
        entity_registry = er.async_get(self.hass)
        utility_meters = []
        
        for device in self._devices:
            device_id = device.get(CONF_DEVICE_ID)
            
            if device_id:
                # New UUID-based unique ID format
                expected_unique_id = f"{device_id}_utility_meter"
            else:
                # Fallback to old format if no UUID (shouldn't happen)
                device_name = device.get("name", "Unknown")
                expected_unique_id = f"{self._config_entry_id}_{sanitize_name(self._group_name)}_utility_meter_{sanitize_name(device_name)}"
            
            # Find entity with this unique ID
            for entity_id, entry in entity_registry.entities.items():
                if (
                    entry.unique_id == expected_unique_id
                    and entry.domain == "sensor"
                    and entry.platform == DOMAIN
                ):
                    utility_meters.append(entity_id)
                    break
        
        return utility_meters
    
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
            
        total = 0
        all_unavailable = True
        
        for entity_id in self._utility_meter_entities:
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
        else:
            self._attr_available = True
            self._attr_native_value = round(total, 3)


class PhantomUtilityMeterSensor(PhantomDeviceSensor, RestoreEntity):
    """Sensor that tracks energy consumption for a device."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "last_value": self._last_value,
            "source_entity": self._energy_entity,
        }
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        device_name: str,
        device_id: str,
        energy_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, device_name, device_id, "utility_meter")
        self.hass = hass
        self._energy_entity = energy_entity
        self._attr_name = f"{device_name} Energy Meter"
        self._last_value = None
        self._total_consumed = 0.0
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Check for migrated state first (from rename)
        _LOGGER.debug("Checking for migrated state for %s (unique_id: %s)", self._device_name, self._attr_unique_id)
        migrated_state = get_migrated_state(self.hass, self._config_entry_id, self._attr_unique_id)
        last_state = None
        
        if migrated_state:
            try:
                self._total_consumed = float(migrated_state["state"])
                self._attr_native_value = self._total_consumed
                # Restore last_value from attributes if available
                if "last_value" in migrated_state.get("attributes", {}):
                    self._last_value = float(migrated_state["attributes"]["last_value"])
                _LOGGER.info(
                    "✓ Restored migrated state for %s: %s kWh (from old entity: %s)",
                    self._device_name,
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
            _LOGGER.debug("No migrated state found for %s", self._device_name)
            # Try to restore from previous state (normal restart)
            last_state = await self.async_get_last_state()
            if last_state is not None:
                if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    try:
                        self._total_consumed = float(last_state.state)
                        self._attr_native_value = self._total_consumed
                        _LOGGER.info(
                            "Restored utility meter for %s: %s kWh",
                            self._device_name,
                            self._total_consumed
                        )
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Could not restore state for %s: %s",
                            self._device_name,
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
        state = self.hass.states.get(self._energy_entity)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._last_value = float(state.state)
                # Convert Wh to kWh if needed
                if state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                    self._last_value = self._last_value / 1000
            except (ValueError, TypeError):
                self._last_value = None
        
        # Also try to restore the last tracked value from attributes
        if last_state and "last_value" in last_state.attributes:
            try:
                self._last_value = float(last_state.attributes["last_value"])
                _LOGGER.debug(
                    "Restored last tracked value for %s: %s",
                    self._device_name,
                    self._last_value
                )
            except (ValueError, TypeError):
                pass
        
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._energy_entity],
                self._handle_state_change,
            )
        )
        
        # Add periodic updates to ensure downstream sensors stay responsive
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._periodic_update,
                UTILITY_METER_UPDATE_INTERVAL
            )
        )
        _LOGGER.debug(
            "Added %s second periodic update for %s utility meter",
            UTILITY_METER_UPDATE_INTERVAL.total_seconds(),
            self._device_name
        )
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entity."""
        new_state = event.data.get("new_state")
        
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
            self.async_write_ha_state()
            return
        
        try:
            # Get the new value
            new_value = float(new_state.state)
            
            # Convert Wh to kWh if needed
            if new_state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR:
                new_value = new_value / 1000
            
            # Calculate consumption
            if self._last_value is not None and new_value >= self._last_value:
                # Normal increase
                consumption = new_value - self._last_value
                self._total_consumed += consumption
            elif self._last_value is not None and new_value < self._last_value:
                # Meter reset or rollover - just use the new value as consumption
                self._total_consumed += new_value
            
            self._last_value = new_value
            self._attr_available = True
            self._attr_native_value = round(self._total_consumed, 3)
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Could not update utility meter: %s", err)
            self._attr_available = False
        
        self.async_write_ha_state()
    
    @callback
    def _periodic_update(self, now) -> None:
        """Force periodic update to ensure downstream sensors stay responsive."""
        # Only update if we have valid data
        if self._attr_available and self._attr_native_value is not None:
            _LOGGER.debug(
                "Periodic update for %s utility meter: %.3f kWh",
                self._device_name,
                self._attr_native_value
            )
            # Force state write to ensure downstream sensors get notified
            self.async_write_ha_state()
    
    async def async_reset(self) -> None:
        """Reset the utility meter."""
        _LOGGER.info("Resetting utility meter for device '%s'", self._device_name)
        self._total_consumed = 0.0
        self._attr_native_value = 0.0
        self._last_value = None
        
        # Get current value of source entity to use as new baseline
        state = self.hass.states.get(self._energy_entity)
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._last_value = float(state.state)
                # Convert Wh to kWh if needed
                if state.attributes.get("unit_of_measurement") == "Wh":
                    self._last_value = self._last_value / 1000
            except (ValueError, TypeError):
                _LOGGER.warning("Could not get current value for reset baseline")
        
        self.async_write_ha_state()