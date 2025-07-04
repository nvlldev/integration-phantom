"""Power sensor implementations for Phantom Power Monitoring."""
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
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .base import PhantomBaseSensor, PhantomDeviceSensor

_LOGGER = logging.getLogger(__name__)


class PhantomPowerSensor(PhantomBaseSensor):
    """Sensor for total power consumption of a group."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:flash"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        power_entities: list[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "power_total")
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
            self._attr_native_value = total


class PhantomIndividualPowerSensor(PhantomDeviceSensor):
    """Sensor for individual device power."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        device_name: str,
        device_id: str,
        power_entity: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, device_name, device_id, "power")
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
                self._attr_native_value = float(state.state)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not convert state to float: %s", state.state)
                self._attr_available = False
                self._attr_native_value = None