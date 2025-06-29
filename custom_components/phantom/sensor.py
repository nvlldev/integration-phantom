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
    ATTR_ENTITY_ID,
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
    ATTR_ENTITIES,
    ATTR_REMAINDER,
    ATTR_UPSTREAM_POWER_ENTITY,
    ATTR_UPSTREAM_ENERGY_ENTITY,
    CONF_ENERGY_ENTITIES,
    CONF_GROUP_NAME,
    CONF_POWER_ENTITIES,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    DEFAULT_GROUP_NAME,
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
    group_name = config.get(CONF_GROUP_NAME, DEFAULT_GROUP_NAME)
    
    if power_entities:
        entities.append(
            PhantomPowerSensor(
                hass,
                config_entry.entry_id,
                group_name,
                power_entities,
                upstream_power_entity,
            )
        )
        
        # Add remainder sensor if upstream power entity is configured
        if upstream_power_entity:
            entities.append(
                PhantomPowerRemainderSensor(
                    hass,
                    config_entry.entry_id,
                    group_name,
                    power_entities,
                    upstream_power_entity,
                )
            )
    
    if energy_entities:
        entities.append(
            PhantomEnergySensor(
                hass,
                config_entry.entry_id,
                group_name,
                energy_entities,
                upstream_energy_entity,
            )
        )
        
        # Add remainder sensor if upstream energy entity is configured
        if upstream_energy_entity:
            entities.append(
                PhantomEnergyRemainderSensor(
                    hass,
                    config_entry.entry_id,
                    group_name,
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
        config_entry_id: str,
        group_name: str,
        entities: list[str],
        upstream_entity: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config_entry_id = config_entry_id
        self._group_name = group_name
        self._entities = entities
        self._upstream_entity = upstream_entity
        self._state = None
        self._available = True
        self._attributes = {}
        
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_id)},
            name=self._group_name,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type. Must be implemented by subclasses."""
        raise NotImplementedError

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry_id}_{self._sensor_type}"

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        # For the main sensors, we'll use descriptive names
        if self._sensor_type == "power":
            return "Power"
        elif self._sensor_type == "energy":
            return "Energy"
        return None

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
        attributes = {
            ATTR_ENTITIES: self._entities,
        }
        if self._upstream_entity:
            # Use appropriate upstream entity attribute based on sensor type
            if self._sensor_type == "power":
                attributes[ATTR_UPSTREAM_POWER_ENTITY] = self._upstream_entity
            elif self._sensor_type == "energy":
                attributes[ATTR_UPSTREAM_ENERGY_ENTITY] = self._upstream_entity
            
            if ATTR_REMAINDER in self._attributes:
                attributes[ATTR_REMAINDER] = self._attributes[ATTR_REMAINDER]
        
        return attributes

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        if last_state := await self.async_get_last_state():
            self._state = last_state.state
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    self._state = float(last_state.state)
                except (ValueError, TypeError):
                    self._state = None

        # Track all entities
        all_entities = self._entities[:]
        if self._upstream_entity:
            all_entities.append(self._upstream_entity)

        self._unsubscribe_listeners.append(
            async_track_state_change_event(
                self.hass,
                all_entities,
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
        """Update the sensor state."""
        total = 0
        available_entities = 0
        
        for entity_id in self._entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    total += value
                    available_entities += 1
                except (ValueError, TypeError):
                    continue
        
        if available_entities == 0:
            self._available = False
            self._state = None
        else:
            self._available = True
            self._state = round(total, 2)
        
        # Calculate remainder if upstream entity is configured
        if self._upstream_entity:
            upstream_state = self.hass.states.get(self._upstream_entity)
            if upstream_state and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    upstream_value = float(upstream_state.state)
                    remainder = upstream_value - total
                    self._attributes[ATTR_REMAINDER] = round(remainder, 2)
                except (ValueError, TypeError):
                    self._attributes.pop(ATTR_REMAINDER, None)
            else:
                self._attributes.pop(ATTR_REMAINDER, None)
        
        self.async_write_ha_state()


class PhantomPowerSensor(PhantomBaseSensor):
    """Phantom power monitoring sensor."""

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        return "power"

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


class PhantomEnergySensor(PhantomBaseSensor):
    """Phantom energy monitoring sensor."""

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        return "energy"

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
        # Default to kWh, but could be made configurable
        return UnitOfEnergy.KILO_WATT_HOUR


class PhantomRemainderBaseSensor(SensorEntity, RestoreEntity):
    """Base class for Phantom remainder sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        entities: list[str],
        upstream_entity: str,
    ) -> None:
        """Initialize the remainder sensor."""
        self.hass = hass
        self._config_entry_id = config_entry_id
        self._group_name = group_name
        self._entities = entities
        self._upstream_entity = upstream_entity
        self._state = None
        self._available = True
        self._group_total = 0
        self._upstream_value = None
        self._group_entities_available = 0
        self._upstream_available = False
        
        self._unsubscribe_listeners = []

    @property
    def has_entity_name(self) -> bool:
        """Return True if entity has a name."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_id)},
            name=self._group_name,
            manufacturer="Phantom",
            model="Power Monitor",
            sw_version="1.0.0",
        )

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type. Must be implemented by subclasses."""
        raise NotImplementedError

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._config_entry_id}_{self._sensor_type}_remainder"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        # Remainder sensors get descriptive names
        if self._sensor_type == "power":
            return "Power remainder"
        elif self._sensor_type == "energy":
            return "Energy remainder"
        return "Remainder"

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
        attributes = {
            ATTR_ENTITIES: self._entities,
            f"upstream_{self._sensor_type}_entity": self._upstream_entity,
            "group_total": self._group_total,
            "group_entities_available": self._group_entities_available,
            "upstream_available": self._upstream_available,
        }
        
        if self._upstream_value is not None:
            attributes["upstream_value"] = self._upstream_value
            
        return attributes

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        if last_state := await self.async_get_last_state():
            self._state = last_state.state
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
        group_total = 0
        available_entities = 0
        
        for entity_id in self._entities:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                try:
                    value = float(state.state)
                    group_total += value
                    available_entities += 1
                except (ValueError, TypeError):
                    continue
        
        # Store group info for attributes
        self._group_total = round(group_total, 2)
        self._group_entities_available = available_entities
        
        # Check upstream availability
        upstream_state = self.hass.states.get(self._upstream_entity)
        upstream_available = (
            upstream_state 
            and upstream_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        )
        self._upstream_available = upstream_available
        
        # Try to get upstream value
        upstream_value = None
        if upstream_available:
            try:
                upstream_value = float(upstream_state.state)
                self._upstream_value = round(upstream_value, 2)
            except (ValueError, TypeError):
                upstream_value = None
                self._upstream_value = None
                upstream_available = False
                self._upstream_available = False
        else:
            self._upstream_value = None
        
        # Sensor is available if we have either group data or upstream data
        if available_entities > 0 or upstream_available:
            self._available = True
            
            # Try to calculate remainder if both are available
            if available_entities > 0 and upstream_available:
                remainder = upstream_value - group_total
                self._state = round(remainder, 2)
            elif upstream_available:
                # Only upstream available, remainder equals upstream value
                self._state = round(upstream_value, 2)
            else:
                # Only group available, remainder is negative of group total
                self._state = round(-group_total, 2)
        else:
            # Neither group nor upstream available
            self._available = False
            self._state = None
        
        self.async_write_ha_state()


class PhantomPowerRemainderSensor(PhantomRemainderBaseSensor):
    """Phantom power remainder sensor."""

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        return "power"

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
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        return "energy"

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