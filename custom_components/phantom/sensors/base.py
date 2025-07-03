"""Base sensor classes for Phantom Power Monitoring."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN
from ..utils import sanitize_name


class PhantomBaseSensor(SensorEntity):
    """Base class for Phantom group sensors."""
    
    _attr_has_entity_name = True
    _attr_should_poll = False
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self._config_entry_id = config_entry_id
        self._group_name = group_name
        self._group_id = group_id
        self._sensor_type = sensor_type
        
        # Use group UUID if available, otherwise fall back to old format
        if group_id:
            self._attr_unique_id = f"{group_id}_{sensor_type}"
        else:
            self._attr_unique_id = f"{config_entry_id}_{sanitize_name(group_name)}_{sensor_type}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._config_entry_id}_{sanitize_name(self._group_name)}")},
            name=f"Phantom {self._group_name}",
            manufacturer="Phantom",
            model="Power Monitor",
        )


class PhantomDeviceSensor(SensorEntity):
    """Base class for Phantom device sensors."""
    
    _attr_has_entity_name = True
    _attr_should_poll = False
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        device_name: str,
        device_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self._config_entry_id = config_entry_id
        self._group_name = group_name
        self._device_name = device_name
        self._device_id = device_id
        self._sensor_type = sensor_type
        
        # Device sensors use device UUID for unique_id
        self._attr_unique_id = f"{device_id}_{sensor_type}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Device sensors belong to the same group device
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._config_entry_id}_{sanitize_name(self._group_name)}")},
            name=f"Phantom {self._group_name}",
            manufacturer="Phantom",
            model="Power Monitor",
        )