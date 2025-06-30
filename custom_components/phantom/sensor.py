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
    
    power_entities = config.get(CONF_POWER_ENTITIES, [])
    energy_entities = config.get(CONF_ENERGY_ENTITIES, [])
    upstream_power_entity = config.get(CONF_UPSTREAM_POWER_ENTITY)
    upstream_energy_entity = config.get(CONF_UPSTREAM_ENERGY_ENTITY)
    
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
            entities.append(
                PhantomUpstreamEnergyMeterSensor(
                    hass,
                    config_entry,
                    upstream_energy_entity,
                )
            )
            
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
            entities.append(
                PhantomUtilityMeterSensor(
                    hass,
                    config_entry,
                    entity_id,
                    energy_entities,
                    upstream_energy_entity,
                )
            )
    
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
        return "Power"

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
        return "Energy"

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

    async def _async_update_state(self) -> None:
        """Update the energy sensor state."""
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
                    _LOGGER.warning("Invalid energy value for %s: %s", entity_id, state.state)
                    continue
        
        if available_count > 0:
            self._available = True
            self._state = round(total, 3)
        else:
            self._available = False
            self._state = None
        
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
        # Extract a clean name from the entity ID
        parts = self._source_entity_id.split('.')[-1].replace('_', ' ')
        return f"{parts.title()} power"

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
        return "Upstream power"

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
        return "Upstream energy meter"

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
        
        # Restore state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                    if last_state.attributes:
                        self._baseline_value = last_state.attributes.get("baseline")
                except (ValueError, TypeError):
                    self._state = 0.0

        # Set initial baseline if needed
        if self._baseline_value is None:
            upstream_state = self.hass.states.get(self._upstream_entity_id)
            if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._baseline_value = float(upstream_state.state)
                    self._last_source_value = self._baseline_value
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
        return "Power remainder"

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
        return "Energy remainder"

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
        
        # Restore last state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Track utility meter entities instead of raw entities
        track_entities = []
        
        # Add individual utility meter entities
        for entity_id in self._entities:
            clean_id = entity_id.replace(".", "_")
            meter_id = f"sensor.{self._config_entry.entry_id}_meter_{clean_id}"
            track_entities.append(meter_id)
        
        # Add upstream utility meter entity
        upstream_meter_id = f"sensor.{self._config_entry.entry_id}_upstream_energy_meter"
        track_entities.append(upstream_meter_id)
        
        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                track_entities,
                self._async_state_changed,
            )
        )
        
        # Initial state update
        await self._async_update_state()

    async def _async_update_state(self) -> None:
        """Update the energy remainder sensor state using utility meter values."""
        # Calculate group total from utility meters
        group_total = 0.0
        group_available = 0
        
        for entity_id in self._entities:
            # Get the utility meter for this entity
            clean_id = entity_id.replace(".", "_")
            meter_id = f"sensor.{self._config_entry.entry_id}_meter_{clean_id}"
            state = self.hass.states.get(meter_id)
            
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    group_total += value
                    group_available += 1
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid utility meter value for %s: %s", meter_id, state.state)
                    continue
        
        # Get upstream utility meter value
        upstream_meter_id = f"sensor.{self._config_entry.entry_id}_upstream_energy_meter"
        upstream_state = self.hass.states.get(upstream_meter_id)
        upstream_value = None
        upstream_available = False
        
        if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                upstream_value = float(upstream_state.state)
                upstream_available = True
            except (ValueError, TypeError):
                _LOGGER.warning("Invalid upstream meter value for %s: %s", upstream_meter_id, upstream_state.state)
        
        # Remainder sensor is only available if BOTH conditions are met:
        # 1. At least one group utility meter is available
        # 2. Upstream utility meter is available
        if group_available > 0 and upstream_available:
            self._available = True
            remainder = upstream_value - group_total
            self._state = round(remainder, 3)
        else:
            # Either no group meters or no upstream meter - sensor unavailable
            self._available = False
            self._state = None
        
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
        # Extract a clean name from the entity ID
        parts = self._source_entity_id.split('.')[-1].replace('_', ' ')
        return f"{parts.title()} meter"

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
        
        # Restore state
        if last_state := await self.async_get_last_state():
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                    if last_state.attributes:
                        self._baseline_value = last_state.attributes.get("baseline")
                except (ValueError, TypeError):
                    self._state = 0.0

        # Set initial baseline if needed
        if self._baseline_value is None:
            source_state = self.hass.states.get(self._source_entity_id)
            if source_state and source_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._baseline_value = float(source_state.state)
                    self._last_source_value = self._baseline_value
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


