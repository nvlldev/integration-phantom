"""Remainder calculation sensor implementations for Phantom Power Monitoring."""
from __future__ import annotations

import asyncio
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
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity

from .base import PhantomBaseSensor
from ..const import CONF_DEVICE_ID, DOMAIN
from ..utils import sanitize_name
from ..repairs import (
    async_create_sensor_unavailable_issue,
    async_delete_sensor_unavailable_issue,
    async_create_upstream_unavailable_issue,
    async_delete_upstream_unavailable_issue,
)

_LOGGER = logging.getLogger(__name__)


class PhantomPowerRemainderSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor for power remainder (upstream - total)."""
    
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:flash-outline"
    
    def __init__(
        self,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_entity: str,
        power_entities: list[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "power_remainder")
        self._upstream_entity = upstream_entity
        self._power_entities = power_entities
        self._attr_name = "Power Remainder"
        self._upstream_issue_created = False
        self._devices_issue_created = False
    
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._attr_native_value = float(last_state.state)
                    self._attr_available = True
                except (ValueError, TypeError):
                    pass
        
        all_entities = [self._upstream_entity] + self._power_entities
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                all_entities,
                self._handle_state_change,
            )
        )
        
        # Do initial update
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
        # Get upstream value
        upstream_state = self.hass.states.get(self._upstream_entity)
        upstream_available = True
        upstream_value = None
        
        if upstream_state is None or upstream_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            upstream_available = False
            
            # Create upstream unavailable issue if not already created
            if not self._upstream_issue_created:
                async_create_upstream_unavailable_issue(
                    self.hass,
                    self._group_name,
                    self._upstream_entity
                )
                self._upstream_issue_created = True
        else:
            try:
                upstream_value = float(upstream_state.state)
                
                # Delete upstream issue if it was created
                if self._upstream_issue_created:
                    async_delete_upstream_unavailable_issue(
                        self.hass,
                        self._group_name
                    )
                    self._upstream_issue_created = False
            except (ValueError, TypeError):
                upstream_available = False
        
        if not upstream_available:
            # Don't update if upstream is not available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = 0.0
            return
        
        # Calculate total from power entities
        total = 0
        any_available = False
        unavailable_entities = []
        
        for entity_id in self._power_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                unavailable_entities.append(entity_id)
                continue
                
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                any_available = True
                try:
                    total += float(state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert state to float: %s", state.state)
            else:
                unavailable_entities.append(entity_id)
        
        if not any_available:
            # Don't update if no devices are available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = 0.0
            
            # Create devices unavailable issue if not already created
            if not self._devices_issue_created:
                async_create_sensor_unavailable_issue(
                    self.hass,
                    "power_remainder",
                    self._attr_name,
                    self._group_name,
                    unavailable_entities
                )
                self._devices_issue_created = True
        else:
            self._attr_available = True
            self._attr_native_value = upstream_value - total
            
            # Delete devices issue if it was created
            if self._devices_issue_created:
                async_delete_sensor_unavailable_issue(
                    self.hass,
                    "power_remainder",
                    self._attr_name,
                    self._group_name
                )
                self._devices_issue_created = False


class PhantomEnergyRemainderSensor(PhantomBaseSensor, RestoreEntity):
    """Sensor for accumulated energy remainder (works like a utility meter)."""
    
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    _attr_icon = "mdi:lightning-bolt-outline"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        upstream_entity: str,
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry_id, group_name, group_id, "energy_remainder")
        self._hass = hass
        self._upstream_entity = upstream_entity
        self._devices = devices
        self._attr_name = "Energy Remainder"
        self._upstream_meter_entity = None
        self._utility_meter_entities = []
        self._setup_delayed = False
        self._upstream_issue_created = False
        self._devices_issue_created = False
        self._last_upstream_value = None
        self._last_total_value = None
        self._accumulated_remainder = 0.0
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        attrs = {
            "upstream_meter": self._upstream_meter_entity,
            "device_count": len(self._utility_meter_entities),
        }
        if self._last_upstream_value is not None and self._last_total_value is not None:
            attrs["instantaneous_remainder"] = self._last_upstream_value - self._last_total_value
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
                    # Always restore the value, regardless of sensor version
                    self._accumulated_remainder = float(last_state.state)
                    self._attr_native_value = self._accumulated_remainder
                    self._attr_available = True
                    
                    # Try to restore tracking values if they exist
                    if "last_upstream_value" in last_state.attributes:
                        self._last_upstream_value = float(last_state.attributes["last_upstream_value"])
                    if "last_total_value" in last_state.attributes:
                        self._last_total_value = float(last_state.attributes["last_total_value"])
                    
                    _LOGGER.info(
                        "Restored energy remainder for '%s': %.3f kWh (upstream: %s, total: %s)",
                        self._group_name,
                        self._accumulated_remainder,
                        self._last_upstream_value if self._last_upstream_value is not None else "None",
                        self._last_total_value if self._last_total_value is not None else "None"
                    )
                except (ValueError, TypeError):
                    self._accumulated_remainder = 0.0
                    self._attr_native_value = 0.0
        else:
            self._accumulated_remainder = 0.0
            self._attr_native_value = 0.0
        
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
            f"{self._config_entry_id}_{sanitize_name(self._group_name)}_upstream_energy_meter",
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
        if self._group_id:
            expected_unique_id = f"{self._group_id}_upstream_energy_meter"
        else:
            expected_unique_id = f"{self._config_entry_id}_{sanitize_name(self._group_name)}_upstream_energy_meter"
        
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
                "Energy remainder '%s' - upstream value is None",
                self._group_name,
            )
            # Don't update if upstream is not available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = 0.0
            
            # Create upstream issue if not already created
            if not self._upstream_issue_created:
                async_create_sensor_unavailable_issue(
                    self.hass,
                    "energy_remainder_upstream",
                    "Upstream Energy Meter",
                    self._group_name,
                    [self._upstream_meter_entity] if self._upstream_meter_entity else []
                )
                self._upstream_issue_created = True
            return
        else:
            # Delete upstream issue if it was created
            if self._upstream_issue_created:
                async_delete_sensor_unavailable_issue(
                    self.hass,
                    "energy_remainder_upstream",
                    "Upstream Energy Meter", 
                    self._group_name
                )
                self._upstream_issue_created = False
        
        # Calculate total from utility meters
        total = 0
        any_available = False
        unavailable_entities = []
        
        for entity_id in self._utility_meter_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                unavailable_entities.append(entity_id)
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
            else:
                unavailable_entities.append(entity_id)
        
        if not any_available:
            _LOGGER.debug(
                "Energy remainder '%s' - no utility meters available",
                self._group_name,
            )
            # Don't update if no devices are available yet
            # Keep previous state during restart
            if not self._attr_available:
                self._attr_native_value = self._accumulated_remainder
            
            # Create devices issue if not already created
            if not self._devices_issue_created:
                async_create_sensor_unavailable_issue(
                    self.hass,
                    "energy_remainder",
                    self._attr_name,
                    self._group_name,
                    unavailable_entities
                )
                self._devices_issue_created = True
            return
        else:
            # Delete devices issue if it was created
            if self._devices_issue_created:
                async_delete_sensor_unavailable_issue(
                    self.hass,
                    "energy_remainder",
                    self._attr_name,
                    self._group_name
                )
                self._devices_issue_created = False
        
        # Now we have both upstream and total values
        # Calculate deltas if we have previous values
        if self._last_upstream_value is not None and self._last_total_value is not None:
            upstream_delta = upstream_value - self._last_upstream_value
            total_delta = total - self._last_total_value
            
            # Only process if there's actual consumption
            if upstream_delta > 0.000001 or total_delta > 0.000001:
                # Calculate the remainder delta
                remainder_delta = upstream_delta - total_delta
                
                # Only accumulate positive remainder (unaccounted energy)
                if remainder_delta > 0:
                    self._accumulated_remainder += remainder_delta
                    _LOGGER.debug(
                        "Energy remainder '%s' - upstream delta: %.3f, total delta: %.3f, remainder delta: %.3f, accumulated: %.3f",
                        self._group_name,
                        upstream_delta,
                        total_delta,
                        remainder_delta,
                        self._accumulated_remainder,
                    )
                else:
                    _LOGGER.debug(
                        "Energy remainder '%s' - devices caught up, not accumulating negative remainder: %.3f",
                        self._group_name,
                        remainder_delta,
                    )
            elif upstream_delta < -0.000001 or total_delta < -0.000001:
                # Handle meter resets - just log it, don't accumulate negative deltas
                _LOGGER.info(
                    "Energy remainder '%s' - meter reset detected (upstream: %.3f->%.3f, total: %.3f->%.3f)",
                    self._group_name,
                    self._last_upstream_value,
                    upstream_value,
                    self._last_total_value,
                    total,
                )
        
        # Update tracking values
        self._last_upstream_value = upstream_value
        self._last_total_value = total
        self._attr_native_value = self._accumulated_remainder
        self._attr_available = True
    
    async def async_reset(self) -> None:
        """Reset the energy remainder accumulator."""
        _LOGGER.info("Resetting energy remainder for group '%s'", self._group_name)
        self._accumulated_remainder = 0.0
        self._attr_native_value = 0.0
        # Keep the last values to continue tracking from current state
        self.async_write_ha_state()