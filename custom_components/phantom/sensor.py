"""Sensor platform for Phantom Power Monitoring with Multi-Group Support."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DEVICES,
    CONF_GROUPS,
    CONF_GROUP_NAME,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    DOMAIN,
)
from .state_migration import get_migrated_state, clear_migration_data


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Phantom sensors."""
    _LOGGER.info("Setting up Phantom sensors for config entry: %s", config_entry.entry_id)
    config = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Config data: %s", config)
    
    entities = []
    
    # Handle both old (single group) and new (multiple groups) format
    if CONF_GROUPS in config:
        # New format - multiple groups
        groups = config.get(CONF_GROUPS, [])
        _LOGGER.info("Setting up Phantom sensors for %d groups", len(groups))
        
        for group_index, group in enumerate(groups):
            group_name = group.get(CONF_GROUP_NAME, f"Group {group_index + 1}")
            devices = group.get(CONF_DEVICES, [])
            upstream_power_entity = group.get(CONF_UPSTREAM_POWER_ENTITY)
            upstream_energy_entity = group.get(CONF_UPSTREAM_ENERGY_ENTITY)
            
            _LOGGER.info(
                "Setting up group '%s' (index %d) with %d devices, upstream_power=%s, upstream_energy=%s",
                group_name,
                group_index,
                len(devices),
                upstream_power_entity,
                upstream_energy_entity
            )
            
            # Create sensors for this group
            try:
                group_entities = await _create_group_sensors(
                    hass,
                    config_entry,
                    group_name,
                    devices,
                    upstream_power_entity,
                    upstream_energy_entity,
                )
                _LOGGER.info("Created %d entities for group '%s'", len(group_entities), group_name)
                entities.extend(group_entities)
            except Exception as e:
                _LOGGER.error("Error creating sensors for group '%s': %s", group_name, e, exc_info=True)
    else:
        # Old format - single group (backward compatibility)
        devices = config.get(CONF_DEVICES, [])
        upstream_power_entity = config.get(CONF_UPSTREAM_POWER_ENTITY)
        upstream_energy_entity = config.get(CONF_UPSTREAM_ENERGY_ENTITY)
        
        _LOGGER.debug("Setting up Phantom sensors - legacy single group mode")
        
        group_entities = await _create_group_sensors(
            hass,
            config_entry,
            "Default",
            devices,
            upstream_power_entity,
            upstream_energy_entity,
        )
        entities.extend(group_entities)
    
    # Add all entities
    if entities:
        async_add_entities(entities)
        
        # Schedule clearing migration data after entities have been initialized
        async def clear_migration_after_delay():
            """Clear migration data after entities have had time to restore states."""
            await asyncio.sleep(2.0)  # Give entities time to initialize and restore states
            clear_migration_data(hass, config_entry.entry_id)
            _LOGGER.debug("Cleared migration data after entity initialization")
        
        hass.async_create_task(clear_migration_after_delay())
    else:
        _LOGGER.warning("No entities created for Phantom integration")


async def _create_group_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    group_name: str,
    devices: list[dict[str, Any]],
    upstream_power_entity: str | None,
    upstream_energy_entity: str | None,
) -> list[SensorEntity]:
    """Create sensors for a single group."""
    _LOGGER.debug("Creating sensors for group '%s'", group_name)
    entities = []
    
    # Collect power and energy entities from devices
    power_entities = []
    energy_entities = []
    individual_power_entities = []
    
    _LOGGER.debug("Processing %d devices for group '%s'", len(devices), group_name)
    
    for device in devices:
        device_name = device.get("name", "Unknown")
        power_entity = device.get("power_entity")
        energy_entity = device.get("energy_entity")
        
        _LOGGER.debug(
            "Device '%s': power_entity=%s, energy_entity=%s",
            device_name,
            power_entity,
            energy_entity
        )
        
        if power_entity:
            power_entities.append(power_entity)
            # Create individual power sensor
            individual_sensor = PhantomIndividualPowerSensor(
                config_entry.entry_id,
                group_name,
                device_name,
                power_entity,
            )
            entities.append(individual_sensor)
            individual_power_entities.append(individual_sensor)
            _LOGGER.debug("Created individual power sensor for device '%s'", device_name)
        
        if energy_entity:
            energy_entities.append(energy_entity)
            # Create individual utility meter sensor
            entities.append(
                PhantomUtilityMeterSensor(
                    hass,
                    config_entry.entry_id,
                    group_name,
                    device_name,
                    energy_entity,
                )
            )
            _LOGGER.debug("Created utility meter sensor for device '%s'", device_name)
    
    # Create group power total sensor
    if power_entities:
        entities.append(
            PhantomPowerSensor(
                config_entry.entry_id,
                group_name,
                power_entities,
            )
        )
        _LOGGER.debug("Created power total sensor for group '%s'", group_name)
    else:
        _LOGGER.debug("No power entities for group '%s', skipping power total sensor", group_name)
    
    # Create group energy total sensor
    if energy_entities:
        entities.append(
            PhantomEnergySensor(
                hass,
                config_entry.entry_id,
                group_name,
                devices,
            )
        )
        _LOGGER.debug("Created energy total sensor for group '%s'", group_name)
    else:
        _LOGGER.debug("No energy entities for group '%s', skipping energy total sensor", group_name)
    
    # Create upstream sensors if configured
    if upstream_power_entity:
        entities.append(
            PhantomUpstreamPowerSensor(
                config_entry.entry_id,
                group_name,
                upstream_power_entity,
            )
        )
        _LOGGER.debug("Created upstream power sensor for group '%s'", group_name)
        
        # Create power remainder if we have both upstream and group power
        if power_entities:
            entities.append(
                PhantomPowerRemainderSensor(
                    config_entry.entry_id,
                    group_name,
                    upstream_power_entity,
                    power_entities,
                )
            )
            _LOGGER.debug("Created power remainder sensor for group '%s'", group_name)
    
    if upstream_energy_entity:
        entities.append(
            PhantomUpstreamEnergyMeterSensor(
                hass,
                config_entry.entry_id,
                group_name,
                upstream_energy_entity,
            )
        )
        _LOGGER.debug("Created upstream energy meter sensor for group '%s'", group_name)
        
        # Create energy remainder if we have both upstream and group energy
        if energy_entities:
            entities.append(
                PhantomEnergyRemainderSensor(
                    hass,
                    config_entry.entry_id,
                    group_name,
                    upstream_energy_entity,
                    devices,
                )
            )
            _LOGGER.debug("Created energy remainder sensor for group '%s'", group_name)
    
    _LOGGER.info("Created total of %d entities for group '%s'", len(entities), group_name)
    return entities


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use in entity IDs."""
    return name.lower().replace(" ", "_").replace("-", "_")


class PhantomBaseSensor(SensorEntity):
    """Base class for Phantom sensors."""
    
    _attr_has_entity_name = True
    _attr_should_poll = False
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self._config_entry_id = config_entry_id
        self._group_name = group_name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{config_entry_id}_{_sanitize_name(group_name)}_{sensor_type}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._config_entry_id}_{_sanitize_name(self._group_name)}")},
            name=f"Phantom {self._group_name}",
            manufacturer="Phantom",
            model="Power Monitor",
            # configuration_url="/phantom",  # Temporarily disabled due to validation error
        )


class PhantomPowerSensor(PhantomBaseSensor):
    """Sensor for total power consumption of a group."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        power_entities: list[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, "power_total")
        self._power_entities = power_entities
        self._attr_name = "Power Total"
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._power_entities,
                self._handle_state_change,
            )
        )
        self._update_state()
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entities."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
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
        else:
            self._attr_available = True
            self._attr_native_value = round(total, 2)


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
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, "energy_total")
        self._hass = hass
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
        entity_registry = er.async_get(self.hass)
        utility_meters = []
        
        for device in self._devices:
            device_name = device.get("name", "Unknown")
            # Generate expected unique ID for utility meter
            expected_unique_id = f"{self._config_entry_id}_{_sanitize_name(self._group_name)}_utility_meter_{_sanitize_name(device_name)}"
            
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


class PhantomIndividualPowerSensor(PhantomBaseSensor):
    """Sensor for individual device power."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        device_name: str,
        power_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_entry_id, 
            group_name, 
            f"power_{_sanitize_name(device_name)}"
        )
        self._device_name = device_name
        self._power_entity = power_entity
        self._attr_name = f"{device_name} Power"
    
    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if not self.available:
            return "mdi:flash-off"
        if self._attr_native_value and self._attr_native_value > 0:
            return "mdi:flash"
        return "mdi:flash-outline"
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._power_entity],
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
        state = self.hass.states.get(self._power_entity)
        
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True
            try:
                self._attr_native_value = round(float(state.state), 2)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not convert state to float: %s", state.state)
                self._attr_available = False
                self._attr_native_value = None


class PhantomUtilityMeterSensor(PhantomBaseSensor, RestoreEntity):
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
        energy_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_entry_id,
            group_name,
            f"utility_meter_{_sanitize_name(device_name)}"
        )
        self._hass = hass
        self._device_name = device_name
        self._energy_entity = energy_entity
        self._attr_name = f"{device_name} Energy Meter"
        self._last_value = None
        self._total_consumed = 0.0
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Check for migrated state first (from rename)
        _LOGGER.debug("Checking for migrated state for %s (unique_id: %s)", self._device_name, self._attr_unique_id)
        migrated_state = get_migrated_state(self._hass, self._config_entry_id, self._attr_unique_id)
        
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
            if (last_state := await self.async_get_last_state()) is not None:
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


class PhantomUpstreamPowerSensor(PhantomBaseSensor):
    """Sensor for upstream power monitoring."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:transmission-tower"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        upstream_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, "upstream_power")
        self._upstream_entity = upstream_entity
        self._attr_name = "Upstream Power"
    
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
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True
            try:
                self._attr_native_value = round(float(state.state), 2)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not convert state to float: %s", state.state)
                self._attr_available = False
                self._attr_native_value = None


class PhantomUpstreamEnergyMeterSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor that tracks upstream energy consumption."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
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
        upstream_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, "upstream_energy_meter")
        self._hass = hass
        self._upstream_entity = upstream_entity
        self._attr_name = "Upstream Energy Meter"
        self._last_value = None
        self._total_consumed = 0.0
    
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
            _LOGGER.warning("Could not update upstream meter: %s", err)
            self._attr_available = False
        
        self.async_write_ha_state()


class PhantomPowerRemainderSensor(PhantomBaseSensor):
    """Sensor for power remainder (upstream - total)."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash-outline"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        upstream_entity: str,
        power_entities: list[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, "power_remainder")
        self._upstream_entity = upstream_entity
        self._power_entities = power_entities
        self._attr_name = "Power Remainder"
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        all_entities = [self._upstream_entity] + self._power_entities
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                all_entities,
                self._handle_state_change,
            )
        )
        self._update_state()
    
    @callback
    def _handle_state_change(self, event) -> None:
        """Handle state changes of tracked entities."""
        self._update_state()
        self.async_write_ha_state()
    
    @callback
    def _update_state(self) -> None:
        """Update the sensor state."""
        # Get upstream value
        upstream_state = self.hass.states.get(self._upstream_entity)
        if upstream_state is None or upstream_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
            self._attr_native_value = None
            return
        
        try:
            upstream_value = float(upstream_state.state)
        except (ValueError, TypeError):
            self._attr_available = False
            self._attr_native_value = None
            return
        
        # Calculate total from power entities
        total = 0
        any_available = False
        
        for entity_id in self._power_entities:
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
            self._attr_native_value = round(upstream_value - total, 2)


class PhantomEnergyRemainderSensor(PhantomBaseSensor):
    """Sensor for energy remainder (upstream - total)."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt-outline"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        upstream_entity: str,
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, "energy_remainder")
        self._hass = hass
        self._upstream_entity = upstream_entity
        self._devices = devices
        self._attr_name = "Energy Remainder"
        self._upstream_meter_entity = None
        self._utility_meter_entities = []
        self._setup_delayed = False
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        # Delay setup to allow meters to be created
        self.hass.async_create_task(self._delayed_setup())
    
    async def _delayed_setup(self) -> None:
        """Set up tracking after a delay."""
        # Check if migration is active
        migration_data = self.hass.data.get("phantom_state_migration", {}).get(self._config_entry_id)
        if migration_data:
            _LOGGER.debug("Migration detected for energy remainder, waiting longer for meters to settle")
            await asyncio.sleep(3)  # Wait longer during migration
        else:
            await asyncio.sleep(2)
        
        # Find upstream meter entity
        self._upstream_meter_entity = await self._find_upstream_meter_entity()
        _LOGGER.debug(
            "Energy remainder for group '%s' - looking for upstream meter with unique_id: %s, found: %s",
            self._group_name,
            f"{self._config_entry_id}_{_sanitize_name(self._group_name)}_upstream_energy_meter",
            self._upstream_meter_entity,
        )
        
        # Find utility meter entities
        self._utility_meter_entities = await self._find_utility_meter_entities()
        _LOGGER.debug(
            "Energy remainder for group '%s' - found %d utility meters",
            self._group_name,
            len(self._utility_meter_entities),
        )
        
        all_entities = []
        if self._upstream_meter_entity:
            all_entities.append(self._upstream_meter_entity)
        all_entities.extend(self._utility_meter_entities)
        
        if all_entities:
            _LOGGER.info(
                "Energy remainder tracking entities for group '%s': upstream=%s, meters=%s",
                self._group_name,
                self._upstream_meter_entity,
                self._utility_meter_entities,
            )
            
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    all_entities,
                    self._handle_state_change,
                )
            )
        else:
            _LOGGER.warning(
                "No entities found for energy remainder tracking in group '%s' - upstream: %s, meters: %s",
                self._group_name,
                self._upstream_meter_entity,
                self._utility_meter_entities,
            )
        
        self._setup_delayed = True
        self._update_state()
        self.async_write_ha_state()
    
    async def _find_upstream_meter_entity(self) -> str | None:
        """Find the upstream meter entity."""
        entity_registry = er.async_get(self.hass)
        
        # Generate expected unique ID for upstream meter
        expected_unique_id = f"{self._config_entry_id}_{_sanitize_name(self._group_name)}_upstream_energy_meter"
        
        _LOGGER.debug(
            "Looking for upstream meter entity with unique_id: %s",
            expected_unique_id,
        )
        
        # Debug: log all our platform's entities
        our_entities = []
        for entity_id, entry in entity_registry.entities.items():
            if entry.platform == DOMAIN and entry.config_entry_id == self._config_entry_id:
                our_entities.append(f"{entity_id} (unique_id: {entry.unique_id})")
        
        _LOGGER.debug(
            "All Phantom entities for this config entry: %s",
            our_entities,
        )
        
        # Find entity with this unique ID
        for entity_id, entry in entity_registry.entities.items():
            if (
                entry.unique_id == expected_unique_id
                and entry.domain == "sensor"
                and entry.platform == DOMAIN
            ):
                return entity_id
        
        return None
    
    async def _find_utility_meter_entities(self) -> list[str]:
        """Find utility meter entities for devices."""
        entity_registry = er.async_get(self.hass)
        utility_meters = []
        
        for device in self._devices:
            device_name = device.get("name", "Unknown")
            # Generate expected unique ID for utility meter
            expected_unique_id = f"{self._config_entry_id}_{_sanitize_name(self._group_name)}_utility_meter_{_sanitize_name(device_name)}"
            
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
        
        # Get upstream meter value
        upstream_value = None
        if self._upstream_meter_entity:
            upstream_state = self.hass.states.get(self._upstream_meter_entity)
            _LOGGER.debug(
                "Energy remainder '%s' - upstream meter state: %s",
                self._group_name,
                upstream_state.state if upstream_state else "None",
            )
            if upstream_state and upstream_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    upstream_value = float(upstream_state.state)
                except (ValueError, TypeError):
                    pass
        
        if upstream_value is None:
            _LOGGER.debug(
                "Energy remainder '%s' - upstream value is None, marking unavailable",
                self._group_name,
            )
            self._attr_available = False
            self._attr_native_value = None
            return
        
        # Calculate total from utility meters
        total = 0
        any_available = False
        
        for entity_id in self._utility_meter_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
                
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                any_available = True
                try:
                    value = float(state.state)
                    total += value
                    _LOGGER.debug(
                        "Energy remainder '%s' - utility meter %s: %s",
                        self._group_name,
                        entity_id,
                        value,
                    )
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert state to float: %s", state.state)
        
        if not any_available:
            _LOGGER.debug(
                "Energy remainder '%s' - no utility meters available, marking unavailable",
                self._group_name,
            )
            self._attr_available = False
            self._attr_native_value = None
        else:
            self._attr_available = True
            remainder = upstream_value - total
            # Energy remainder should not go negative
            self._attr_native_value = round(max(0, remainder), 3)
            _LOGGER.debug(
                "Energy remainder '%s' - calculated: %s - %s = %s",
                self._group_name,
                upstream_value,
                total,
                self._attr_native_value,
            )