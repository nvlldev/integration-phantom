"""Sensor platform for Phantom Power Monitoring."""
from __future__ import annotations

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

from .const import (
    CONF_DEVICES,
    CONF_ENERGY_ENTITIES,
    CONF_POWER_ENTITIES,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Phantom sensors."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Handle both new device-based config and legacy entity lists
    devices = config.get(CONF_DEVICES, [])
    power_entities = config.get(CONF_POWER_ENTITIES, [])
    energy_entities = config.get(CONF_ENERGY_ENTITIES, [])
    upstream_power_entity = config.get(CONF_UPSTREAM_POWER_ENTITY)
    upstream_energy_entity = config.get(CONF_UPSTREAM_ENERGY_ENTITY)
    
    # If we have devices configuration, use that; otherwise fall back to legacy
    if devices:
        _LOGGER.debug("Using device-based configuration with %d devices", len(devices))
        # Extract entity lists from devices for backward compatibility
        if not power_entities:
            power_entities = [device["power_entity"] for device in devices if device.get("power_entity")]
        if not energy_entities:
            energy_entities = [device["energy_entity"] for device in devices if device.get("energy_entity")]
    else:
        _LOGGER.debug("Using legacy entity list configuration")
    
    _LOGGER.debug("Setting up Phantom sensors - config_entry_id: %s", config_entry.entry_id)
    _LOGGER.debug("Power entities: %s", power_entities)
    _LOGGER.debug("Energy entities: %s", energy_entities)
    _LOGGER.debug("Upstream power: %s", upstream_power_entity)
    _LOGGER.debug("Upstream energy: %s", upstream_energy_entity)
    
    # Power sensors
    if power_entities:
        # Individual power meters for each power entity
        for entity_id in power_entities:
            entities.append(
                PhantomIndividualPowerSensor(
                    hass,
                    config_entry,
                    entity_id,
                    power_entities,
                    upstream_power_entity,
                )
            )
        
        # Power group total
        entities.append(
            PhantomPowerSensor(
                hass,
                config_entry,
                power_entities,
            )
        )
        
        # Power remainder if upstream configured
        if upstream_power_entity:
            # Add upstream power sensor
            entities.append(
                PhantomUpstreamPowerSensor(
                    hass,
                    config_entry,
                    upstream_power_entity,
                )
            )
            
            entities.append(
                PhantomPowerRemainderSensor(
                    hass,
                    config_entry,
                    power_entities,
                    upstream_power_entity,
                )
            )
    
    # Energy sensors
    if energy_entities:
        # Energy group total
        entities.append(
            PhantomEnergySensor(
                hass,
                config_entry,
                energy_entities,
            )
        )
        
        # Energy remainder if upstream configured
        if upstream_energy_entity:
            # Add upstream energy utility meter
            _LOGGER.debug("Creating upstream energy meter for entity: %s", upstream_energy_entity)
            entities.append(
                PhantomUpstreamEnergyMeterSensor(
                    hass,
                    config_entry,
                    upstream_energy_entity,
                )
            )
            
            _LOGGER.debug("Creating energy remainder sensor")
            entities.append(
                PhantomEnergyRemainderSensor(
                    hass,
                    config_entry,
                    energy_entities,
                    upstream_energy_entity,
                )
            )
        
        # Individual utility meters for each energy entity
        for entity_id in energy_entities:
            _LOGGER.debug("Creating utility meter for entity: %s", entity_id)
            entities.append(
                PhantomUtilityMeterSensor(
                    hass,
                    config_entry,
                    entity_id,
                    energy_entities,
                    upstream_energy_entity,
                )
            )
    
    _LOGGER.debug("Adding %d entities to Home Assistant", len(entities))
    async_add_entities(entities)


class PhantomBaseSensor(SensorEntity, RestoreEntity):
    """Base class for Phantom sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        entities: list[str],
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entities = entities
        self._state = None
        self._available = True
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def should_poll(self) -> bool:
        """Return False as we handle updates via state change events."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "entities": self._entities,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore last state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Track entity state changes
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                self._entities,
                self._async_state_changed,
            )
        )
        
        # Initial state update
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the sensor state. Must be implemented by subclasses."""
        raise NotImplementedError


class PhantomPowerSensor(PhantomBaseSensor):
    """Phantom power group sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry.entry_id}_power"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Power Total"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.POWER

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfPower.WATT

    async def _async_update_state(self) -> None:
        """Update the power sensor state."""
        total = 0.0
        available_count = 0
        
        for entity_id in self._entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    total += value
                    available_count += 1
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid power value for %s: %s", entity_id, state.state)
                    continue
        
        if available_count > 0:
            self._available = True
            self._state = round(total, 2)
        else:
            self._available = False
            self._state = None
        
        self.async_write_ha_state()


class PhantomEnergySensor(PhantomBaseSensor):
    """Phantom energy group sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry.entry_id}_energy"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Energy Total"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    def _find_utility_meter_entities(self) -> list[str]:
        """Find utility meter entity IDs by searching the entity registry."""
        from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
        
        entity_registry = async_get_entity_registry(self.hass)
        utility_meter_entities = []
        
        # Look for entities with our unique IDs
        for entity_id in self._entities:
            clean_id = entity_id.replace(".", "_")
            expected_unique_id = f"{self._config_entry.entry_id}_meter_{clean_id}"
            
            # Find entity with this unique ID
            for ent_id, entry in entity_registry.entities.items():
                if entry.unique_id == expected_unique_id:
                    utility_meter_entities.append(ent_id)
                    _LOGGER.debug("Found utility meter entity for energy total: %s (unique_id: %s)", ent_id, expected_unique_id)
                    break
        
        return utility_meter_entities

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Don't call super() to avoid the base class implementation
        await SensorEntity.async_added_to_hass(self)
        await RestoreEntity.async_added_to_hass(self)
        
        # Restore last state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Set up a delay to allow utility meters to be registered first
        self.hass.async_create_task(self._setup_tracking_with_delay())

    async def _setup_tracking_with_delay(self) -> None:
        """Set up tracking after a delay to allow utility meters to be created."""
        import asyncio
        
        # Wait a bit for utility meters to be registered
        await asyncio.sleep(2)
        
        # Find utility meter entities
        utility_meter_entities = self._find_utility_meter_entities()
        
        _LOGGER.debug("Energy total (delayed) tracking utility meter entities: %s", utility_meter_entities)
        
        if utility_meter_entities:
            self._unsubscribe_listeners.append(
                async_track_state_change_event(
                    self.hass,
                    utility_meter_entities,
                    self._async_state_changed,
                )
            )
        
        # Initial state update
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the energy sensor state by summing utility meters."""
        # Find utility meter entities
        utility_meter_entities = self._find_utility_meter_entities()
        
        total = 0.0
        available_count = 0
        
        _LOGGER.debug("Energy total sensor update - checking %d utility meters", len(utility_meter_entities))
        
        for meter_id in utility_meter_entities:
            state = self.hass.states.get(meter_id)
            _LOGGER.debug("Utility meter %s: %s", meter_id, state.state if state else "Not found")
            
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    total += value
                    available_count += 1
                    _LOGGER.debug("Added %f from meter %s to energy total", value, meter_id)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid utility meter value for %s: %s", meter_id, state.state)
                    continue
        
        if available_count > 0:
            self._available = True
            self._state = round(total, 3)
            _LOGGER.debug("Energy total calculated from utility meters: %f", self._state)
        else:
            self._available = False
            self._state = None
            _LOGGER.debug("Energy total unavailable - no valid utility meters")
        
        self.async_write_ha_state()


class PhantomRemainderBaseSensor(SensorEntity, RestoreEntity):
    """Base class for Phantom remainder sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        entities: list[str],
        upstream_entity: str,
    ) -> None:
        """Initialize the remainder sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._entities = entities
        self._upstream_entity = upstream_entity
        self._state = None
        self._available = True
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def should_poll(self) -> bool:
        """Return False as we handle updates via state change events."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "entities": self._entities,
            "upstream_entity": self._upstream_entity,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore last state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Track all entities including upstream
        all_entities = self._entities + [self._upstream_entity]
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                all_entities,
                self._async_state_changed,
            )
        )
        
        # Initial state update
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the remainder sensor state."""
        # Calculate group total
        group_total = 0.0
        group_available = 0
        
        for entity_id in self._entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    group_total += value
                    group_available += 1
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid value for %s: %s", entity_id, state.state)
                    continue
        
        # Get upstream value
        upstream_state = self.hass.states.get(self._upstream_entity)
        upstream_value = None
        upstream_available = False
        
        if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                upstream_value = float(upstream_state.state)
                upstream_available = True
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid upstream value for %s: %s", self._upstream_entity, upstream_state.state)
        
        # Remainder sensor is only available if BOTH conditions are met:
        # 1. At least one group entity is available
        # 2. Upstream entity is available
        if group_available > 0 and upstream_available:
            self._available = True
            remainder = upstream_value - group_total
            self._state = round(remainder, 3)
        else:
            # Either no group entities or no upstream - sensor unavailable
            self._available = False
            self._state = None
        
        self.async_write_ha_state()


class PhantomIndividualPowerSensor(SensorEntity, RestoreEntity):
    """Individual power sensor with percentage calculations."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        source_entity_id: str,
        group_entities: list[str],
        upstream_entity_id: str | None,
    ) -> None:
        """Initialize the individual power sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._source_entity_id = source_entity_id
        self._group_entities = group_entities
        self._upstream_entity_id = upstream_entity_id
        self._state = None
        self._available = True
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        clean_id = self._source_entity_id.replace(".", "_")
        return f"{self._config_entry.entry_id}_power_{clean_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        # Get the friendly name from the source entity if available
        source_state = self.hass.states.get(self._source_entity_id)
        if source_state and source_state.attributes.get("friendly_name"):
            device_name = source_state.attributes["friendly_name"]
        else:
            # Fall back to processing entity ID
            parts = self._source_entity_id.split('.')[-1].replace('_', ' ')
            device_name = self._convert_to_camel_case(parts)
        
        return f"{device_name} Power"
    
    def _convert_to_camel_case(self, text: str) -> str:
        """Convert text to proper camel case, preserving known device names."""
        # Common device/brand names that should maintain specific capitalization
        special_cases = {
            'idrac': 'iDRAC',
            'ups': 'UPS', 
            'tv': 'TV',
            'pc': 'PC',
            'hvac': 'HVAC',
            'led': 'LED',
            'cpu': 'CPU',
            'gpu': 'GPU',
            'ssd': 'SSD',
            'hdd': 'HDD',
            'wifi': 'WiFi',
            'iot': 'IoT',
            'api': 'API',
            'dns': 'DNS',
            'dhcp': 'DHCP',
            'poe': 'PoE',
            'pdu': 'PDU',
            'nas': 'NAS',
            'raid': 'RAID'
        }
        
        words = text.split()
        result = []
        
        for word in words:
            word_lower = word.lower()
            if word_lower in special_cases:
                result.append(special_cases[word_lower])
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)

    @property
    def should_poll(self) -> bool:
        """Return False as we handle updates via state change events."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.POWER

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfPower.WATT

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {"source_entity": self._source_entity_id}
        
        # Calculate percentages
        if self._state is not None and self._state > 0:
            # Get group total
            group_total = 0.0
            for entity_id in self._group_entities:
                state = self.hass.states.get(entity_id)
                if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    try:
                        group_total += float(state.state)
                    except (ValueError, TypeError):
                        pass
            
            if group_total > 0:
                attributes["percent_of_group"] = round((self._state / group_total) * 100, 1)
            
            # Get upstream value if configured
            if self._upstream_entity_id:
                upstream_state = self.hass.states.get(self._upstream_entity_id)
                if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    try:
                        upstream_value = float(upstream_state.state)
                        if upstream_value > 0:
                            attributes["percent_of_upstream"] = round((self._state / upstream_value) * 100, 1)
                    except (ValueError, TypeError):
                        pass
        
        return attributes

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Track source entity changes
        track_entities = [self._source_entity_id] + self._group_entities
        if self._upstream_entity_id:
            track_entities.append(self._upstream_entity_id)
            
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                track_entities,
                self._async_state_changed,
            )
        )
        
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the individual power sensor state."""
        source_state = self.hass.states.get(self._source_entity_id)
        
        if not source_state or source_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._available = False
            self._state = None
        else:
            try:
                self._state = float(source_state.state)
                self._available = True
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid power value for %s: %s", self._source_entity_id, source_state.state)
                self._available = False
                self._state = None
        
        self.async_write_ha_state()


class PhantomUpstreamPowerSensor(SensorEntity, RestoreEntity):
    """Upstream power sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        upstream_entity_id: str,
    ) -> None:
        """Initialize the upstream power sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._upstream_entity_id = upstream_entity_id
        self._state = None
        self._available = True
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry.entry_id}_upstream_power"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Upstream Power"

    @property
    def should_poll(self) -> bool:
        """Return False as we handle updates via state change events."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.POWER

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfPower.WATT

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"source_entity": self._upstream_entity_id}

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Track upstream entity
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                [self._upstream_entity_id],
                self._async_state_changed,
            )
        )
        
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the upstream power sensor state."""
        upstream_state = self.hass.states.get(self._upstream_entity_id)
        
        if not upstream_state or upstream_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._available = False
            self._state = None
        else:
            try:
                self._state = float(upstream_state.state)
                self._available = True
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid upstream power value for %s: %s", self._upstream_entity_id, upstream_state.state)
                self._available = False
                self._state = None
        
        self.async_write_ha_state()


class PhantomUpstreamEnergyMeterSensor(SensorEntity, RestoreEntity):
    """Upstream energy utility meter sensor that starts at 0."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        upstream_entity_id: str,
    ) -> None:
        """Initialize the upstream energy meter sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._upstream_entity_id = upstream_entity_id
        self._state = 0.0
        self._available = True
        self._baseline_value = None
        self._last_source_value = None
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry.entry_id}_upstream_energy_meter"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Upstream Energy Meter"

    @property
    def should_poll(self) -> bool:
        """Return False as we handle updates via state change events."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {"source_entity": self._upstream_entity_id}
        if self._baseline_value is not None:
            attributes["baseline"] = self._baseline_value
        return attributes

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        _LOGGER.debug("Upstream energy meter sensor %s added to hass for source %s", self.unique_id, self._upstream_entity_id)
        
        # Always start fresh - don't restore state for upstream energy meter
        # This ensures the meter resets when integration is recreated
        self._state = 0.0
        
        # Always set new baseline from current upstream value
        upstream_state = self.hass.states.get(self._upstream_entity_id)
        if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                baseline_value = float(upstream_state.state)
                # Check unit of measurement and convert if needed
                source_unit = upstream_state.attributes.get("unit_of_measurement", "").lower()
                if source_unit in ["wh", "w·h", "w-h"]:
                    # Convert Wh to kWh
                    baseline_value = baseline_value / 1000.0
                self._baseline_value = baseline_value
                self._last_source_value = self._baseline_value
                _LOGGER.debug("Set fresh baseline for upstream %s: %f", self._upstream_entity_id, self._baseline_value)
            except (ValueError, TypeError):
                self._baseline_value = 0.0
                self._last_source_value = 0.0
        else:
            self._baseline_value = 0.0
            self._last_source_value = 0.0

        # Track upstream entity
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                [self._upstream_entity_id],
                self._async_state_changed,
            )
        )
        
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the upstream energy meter state."""
        upstream_state = self.hass.states.get(self._upstream_entity_id)
        
        if not upstream_state or upstream_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._available = False
            return
        
        try:
            current_value = float(upstream_state.state)
            
            # Check unit of measurement and convert if needed
            source_unit = upstream_state.attributes.get("unit_of_measurement", "").lower()
            if source_unit in ["wh", "w·h", "w-h"]:
                # Convert Wh to kWh
                current_value = current_value / 1000.0
            
            # Detect reset (significant decrease)
            if (self._last_source_value is not None and 
                current_value < self._last_source_value - 1.0):
                # Adjust baseline to account for reset
                usage_before_reset = self._last_source_value - self._baseline_value
                self._baseline_value = current_value - usage_before_reset
            
            # Calculate usage since baseline
            usage = current_value - self._baseline_value
            if usage >= 0:
                self._state = round(usage, 3)
                self._available = True
            else:
                # Negative usage indicates a problem, reset
                self._baseline_value = current_value
                self._state = 0.0
                self._available = True
            
            self._last_source_value = current_value
            
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid upstream energy value for %s: %s", self._upstream_entity_id, upstream_state.state)
            self._available = False
        
        self.async_write_ha_state()


class PhantomPowerRemainderSensor(PhantomRemainderBaseSensor):
    """Phantom power remainder sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry.entry_id}_power_remainder"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Power Remainder"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.POWER

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfPower.WATT


class PhantomEnergyRemainderSensor(PhantomRemainderBaseSensor):
    """Phantom energy remainder sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry.entry_id}_energy_remainder"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Energy Remainder"

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        _LOGGER.debug("Energy remainder sensor %s added to hass", self.unique_id)
        
        # Restore last state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Set up a delay to allow utility meters to be registered first
        self.hass.async_create_task(self._setup_tracking_with_delay())

    async def _setup_tracking_with_delay(self) -> None:
        """Set up tracking after a delay to allow utility meters to be created."""
        import asyncio
        
        # Wait a bit for utility meters to be registered
        await asyncio.sleep(2)
        
        # Track utility meter entities instead of raw entities
        track_entities = []
        
        # Find actual utility meter entity IDs
        utility_meter_entities = self._find_utility_meter_entities()
        track_entities.extend(utility_meter_entities)
        
        # Find upstream utility meter entity
        upstream_meter_entity = self._find_upstream_meter_entity()
        if upstream_meter_entity:
            track_entities.append(upstream_meter_entity)
        
        _LOGGER.debug("Energy remainder (delayed) tracking entities: %s", track_entities)
        
        if track_entities:
            self._unsubscribe_listeners.append(
                async_track_state_change_event(
                    self.hass,
                    track_entities,
                    self._async_state_changed,
                )
            )
        
        # Initial state update
        await self._async_update_state()

    def _find_utility_meter_entities(self) -> list[str]:
        """Find utility meter entity IDs by searching the entity registry."""
        from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
        
        entity_registry = async_get_entity_registry(self.hass)
        utility_meter_entities = []
        
        _LOGGER.debug("Looking for utility meter entities in registry with %d total entities", len(entity_registry.entities))
        
        # Look for entities with our unique IDs
        for entity_id in self._entities:
            clean_id = entity_id.replace(".", "_")
            expected_unique_id = f"{self._config_entry.entry_id}_meter_{clean_id}"
            
            _LOGGER.debug("Searching for utility meter with unique_id: %s", expected_unique_id)
            
            # Find entity with this unique ID
            for ent_id, entry in entity_registry.entities.items():
                if entry.unique_id == expected_unique_id:
                    utility_meter_entities.append(ent_id)
                    _LOGGER.debug("Found utility meter entity: %s (unique_id: %s)", ent_id, expected_unique_id)
                    break
            else:
                _LOGGER.debug("Could not find utility meter entity for unique_id: %s", expected_unique_id)
                # Debug: show similar unique IDs
                similar_ids = [entry.unique_id for entry in entity_registry.entities.values() 
                             if entry.unique_id and self._config_entry.entry_id in entry.unique_id]
                _LOGGER.debug("Similar unique IDs in registry: %s", similar_ids)
        
        return utility_meter_entities

    def _find_upstream_meter_entity(self) -> str | None:
        """Find upstream energy meter entity ID."""
        from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
        
        entity_registry = async_get_entity_registry(self.hass)
        expected_unique_id = f"{self._config_entry.entry_id}_upstream_energy_meter"
        
        _LOGGER.debug("Searching for upstream meter with unique_id: %s", expected_unique_id)
        
        # Find entity with this unique ID
        for ent_id, entry in entity_registry.entities.items():
            if entry.unique_id == expected_unique_id:
                _LOGGER.debug("Found upstream meter entity: %s (unique_id: %s)", ent_id, expected_unique_id)
                return ent_id
        
        _LOGGER.debug("Could not find upstream meter entity for unique_id: %s", expected_unique_id)
        # Debug: show similar unique IDs
        similar_ids = [entry.unique_id for entry in entity_registry.entities.values() 
                     if entry.unique_id and self._config_entry.entry_id in entry.unique_id]
        _LOGGER.debug("Similar unique IDs in registry: %s", similar_ids)
        return None

    async def _async_update_state(self) -> None:
        """Update the energy remainder sensor state using utility meter values."""
        # Find utility meter entities
        utility_meter_entities = self._find_utility_meter_entities()
        upstream_meter_entity = self._find_upstream_meter_entity()
        
        # Calculate group total from utility meters
        group_total = 0.0
        group_available = 0
        
        _LOGGER.debug("Energy remainder update - found %d utility meter entities", len(utility_meter_entities))
        
        for meter_id in utility_meter_entities:
            state = self.hass.states.get(meter_id)
            
            _LOGGER.debug("Checking utility meter %s: %s", meter_id, state.state if state else "Not found")
            
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    group_total += value
                    group_available += 1
                    _LOGGER.debug("Added %f from %s to group total", value, meter_id)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid utility meter value for %s: %s", meter_id, state.state)
                    continue
        
        # Get upstream utility meter value
        upstream_value = None
        upstream_available = False
        
        if upstream_meter_entity:
            upstream_state = self.hass.states.get(upstream_meter_entity)
            _LOGGER.debug("Checking upstream meter %s: %s", upstream_meter_entity, upstream_state.state if upstream_state else "Not found")
            
            if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    upstream_value = float(upstream_state.state)
                    upstream_available = True
                    _LOGGER.debug("Upstream meter value: %f", upstream_value)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid upstream meter value for %s: %s", upstream_meter_entity, upstream_state.state)
        else:
            _LOGGER.debug("No upstream meter entity found")
        
        _LOGGER.debug("Energy remainder: group_available=%d, upstream_available=%s", group_available, upstream_available)
        
        # Remainder sensor is only available if BOTH conditions are met:
        # 1. At least one group utility meter is available
        # 2. Upstream utility meter is available
        if group_available > 0 and upstream_available:
            self._available = True
            remainder = upstream_value - group_total
            self._state = round(remainder, 3)
            _LOGGER.debug("Energy remainder calculated: %f", self._state)
        else:
            # Either no group meters or no upstream meter - sensor unavailable
            self._available = False
            self._state = None
            _LOGGER.debug("Energy remainder unavailable - group_available=%d, upstream_available=%s", 
                         group_available, upstream_available)
        
        self.async_write_ha_state()


class PhantomUtilityMeterSensor(SensorEntity, RestoreEntity):
    """Individual utility meter sensor that tracks energy usage from setup."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        source_entity_id: str,
        group_entities: list[str],
        upstream_entity_id: str | None,
    ) -> None:
        """Initialize the utility meter sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._source_entity_id = source_entity_id
        self._group_entities = group_entities
        self._upstream_entity_id = upstream_entity_id
        self._state = 0.0
        self._available = True
        self._baseline_value = None
        self._last_source_value = None
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        # Clean entity ID for use in unique ID
        clean_id = self._source_entity_id.replace(".", "_")
        return f"{self._config_entry.entry_id}_meter_{clean_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        # Get the friendly name from the source entity if available
        source_state = self.hass.states.get(self._source_entity_id)
        if source_state and source_state.attributes.get("friendly_name"):
            device_name = source_state.attributes["friendly_name"]
        else:
            # Fall back to processing entity ID
            parts = self._source_entity_id.split('.')[-1].replace('_', ' ')
            device_name = self._convert_to_camel_case(parts)
        
        return f"{device_name} Energy Meter"
    
    def _convert_to_camel_case(self, text: str) -> str:
        """Convert text to proper camel case, preserving known device names."""
        # Common device/brand names that should maintain specific capitalization
        special_cases = {
            'idrac': 'iDRAC',
            'ups': 'UPS', 
            'tv': 'TV',
            'pc': 'PC',
            'hvac': 'HVAC',
            'led': 'LED',
            'cpu': 'CPU',
            'gpu': 'GPU',
            'ssd': 'SSD',
            'hdd': 'HDD',
            'wifi': 'WiFi',
            'iot': 'IoT',
            'api': 'API',
            'dns': 'DNS',
            'dhcp': 'DHCP',
            'poe': 'PoE',
            'pdu': 'PDU',
            'nas': 'NAS',
            'raid': 'RAID'
        }
        
        words = text.split()
        result = []
        
        for word in words:
            word_lower = word.lower()
            if word_lower in special_cases:
                result.append(special_cases[word_lower])
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)

    @property
    def should_poll(self) -> bool:
        """Return False as we handle updates via state change events."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class."""
        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {"source_entity": self._source_entity_id}
        if self._baseline_value is not None:
            attributes["baseline"] = self._baseline_value
        
        # Calculate percentages based on source entity value
        if self._state is not None and self._state > 0:
            source_state = self.hass.states.get(self._source_entity_id)
            if source_state and source_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    source_value = float(source_state.state)
                    
                    # Get group total from source entities
                    group_total = 0.0
                    for entity_id in self._group_entities:
                        state = self.hass.states.get(entity_id)
                        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                            try:
                                group_total += float(state.state)
                            except (ValueError, TypeError):
                                pass
                    
                    if group_total > 0:
                        attributes["percent_of_group"] = round((source_value / group_total) * 100, 1)
                    
                    # Get upstream value if configured
                    if self._upstream_entity_id:
                        upstream_state = self.hass.states.get(self._upstream_entity_id)
                        if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                            try:
                                upstream_value = float(upstream_state.state)
                                if upstream_value > 0:
                                    attributes["percent_of_upstream"] = round((source_value / upstream_value) * 100, 1)
                            except (ValueError, TypeError):
                                pass
                except (ValueError, TypeError):
                    pass
        
        return attributes

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        _LOGGER.debug("Utility meter sensor %s added to hass for source %s", self.unique_id, self._source_entity_id)
        
        # Always start fresh - don't restore state for utility meters
        # This ensures the meter resets when integration is recreated
        self._state = 0.0
        
        # Always set new baseline from current source value
        source_state = self.hass.states.get(self._source_entity_id)
        if source_state and source_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                baseline_value = float(source_state.state)
                # Check unit of measurement and convert if needed
                source_unit = source_state.attributes.get("unit_of_measurement", "").lower()
                if source_unit in ["wh", "w·h", "w-h"]:
                    # Convert Wh to kWh
                    baseline_value = baseline_value / 1000.0
                self._baseline_value = baseline_value
                self._last_source_value = self._baseline_value
                _LOGGER.debug("Set fresh baseline for %s: %f", self._source_entity_id, self._baseline_value)
            except (ValueError, TypeError):
                self._baseline_value = 0.0
                self._last_source_value = 0.0
        else:
            self._baseline_value = 0.0
            self._last_source_value = 0.0

        # Track source entity changes
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._async_state_changed,
            )
        )
        
        await self._async_update_state()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for unsubscribe in self._unsubscribe_listeners:
            unsubscribe()
        self._unsubscribe_listeners.clear()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state changes."""
        self.hass.async_create_task(self._async_update_state())

    async def _async_update_state(self) -> None:
        """Update the utility meter state."""
        source_state = self.hass.states.get(self._source_entity_id)
        
        if not source_state or source_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._available = False
            return
        
        try:
            current_value = float(source_state.state)
            
            # Check unit of measurement and convert if needed
            source_unit = source_state.attributes.get("unit_of_measurement", "").lower()
            if source_unit in ["wh", "w·h", "w-h"]:
                # Convert Wh to kWh
                current_value = current_value / 1000.0
            
            # Detect reset (significant decrease)
            if (self._last_source_value is not None and 
                current_value < self._last_source_value - 1.0):
                # Adjust baseline to account for reset
                usage_before_reset = self._last_source_value - self._baseline_value
                self._baseline_value = current_value - usage_before_reset
            
            # Calculate usage since baseline
            usage = current_value - self._baseline_value
            if usage >= 0:
                self._state = round(usage, 3)
                self._available = True
            else:
                # Negative usage indicates a problem, reset
                self._baseline_value = current_value
                self._state = 0.0
                self._available = True
            
            self._last_source_value = current_value
            
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid utility meter value for %s: %s", self._source_entity_id, source_state.state)
            self._available = False
        
        self.async_write_ha_state()


