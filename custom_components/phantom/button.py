"""Button platform for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_GROUPS,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_DEVICES,
    CONF_DEVICE_ID,
)
from .utils import sanitize_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Phantom button entities."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    
    for group in config.get(CONF_GROUPS, []):
        group_name = group.get(CONF_GROUP_NAME)
        group_id = group.get(CONF_GROUP_ID)
        
        if group_name:
            entities.append(
                PhantomResetButton(
                    hass,
                    config_entry.entry_id,
                    group_name,
                    group_id,
                    group.get(CONF_DEVICES, []),
                )
            )
    
    async_add_entities(entities)


class PhantomResetButton(ButtonEntity):
    """Button to reset all utility meters in a group."""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:restart"
    
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        group_name: str,
        group_id: str | None,
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the button."""
        self._hass = hass
        self._config_entry_id = config_entry_id
        self._group_name = group_name
        self._group_id = group_id
        self._devices = devices
        self._attr_name = "Reset Energy Meters"
        
        # Use group UUID for unique ID if available
        if group_id:
            self._attr_unique_id = f"{group_id}_reset_button"
        else:
            self._attr_unique_id = f"{config_entry_id}_{sanitize_name(group_name)}_reset_button"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._config_entry_id}_{sanitize_name(self._group_name)}")},
            name=f"Phantom {self._group_name}",
            manufacturer="Phantom",
            model="Power Monitor",
        )
    
    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Reset button pressed for group '%s' (id: %s)", self._group_name, self._group_id)
        
        # Get entities for this group
        entities_by_group = (
            self._hass.data.get(DOMAIN, {})
            .get(self._config_entry_id, {})
            .get("entities_by_group", {})
        )
        
        group_entities = entities_by_group.get(self._group_name, [])
        _LOGGER.info("Found %d resetable entities for group '%s'", len(group_entities), self._group_name)
        
        # Reset each entity
        reset_count = 0
        for entity in group_entities:
            try:
                if hasattr(entity, "async_reset"):
                    await entity.async_reset()
                    reset_count += 1
                    entity_id = getattr(entity, "entity_id", "unknown")
                    _LOGGER.info("Reset utility meter: %s", entity_id)
                else:
                    _LOGGER.warning("Entity does not have async_reset method: %s", entity)
            except Exception as e:
                entity_id = getattr(entity, "entity_id", "unknown")
                _LOGGER.error("Failed to reset entity %s: %s", entity_id, e)
        
        _LOGGER.info(
            "Successfully reset %d utility meters for group '%s'",
            reset_count,
            self._group_name
        )