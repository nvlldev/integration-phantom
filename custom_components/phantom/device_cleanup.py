"""Device cleanup utilities for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, CONF_GROUPS, CONF_GROUP_NAME

_LOGGER = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use in entity IDs."""
    return name.lower().replace(" ", "_").replace("-", "_")


async def async_cleanup_devices_and_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    config: dict[str, Any],
) -> None:
    """Remove devices and entities that no longer exist in the config."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    
    # Get current group names from config
    current_group_names = set()
    if CONF_GROUPS in config:
        for group in config.get(CONF_GROUPS, []):
            group_name = group.get(CONF_GROUP_NAME, "")
            if group_name:
                current_group_names.add(_sanitize_name(group_name))
    else:
        # Legacy single group
        current_group_names.add("default")
    
    _LOGGER.debug("Current group names: %s", current_group_names)
    
    # Find all devices for this config entry
    devices_to_remove = []
    for device_entry in device_registry.devices.values():
        # Check if this device belongs to our integration
        if (DOMAIN, config_entry_id) in device_entry.config_entries:
            # Check if it's a group device
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN and identifier[1].startswith(f"{config_entry_id}_"):
                    # Extract group name from identifier
                    # Format: (DOMAIN, "{config_entry_id}_{sanitized_group_name}")
                    parts = identifier[1].split("_", 1)
                    if len(parts) == 2:
                        device_group_name = parts[1]
                        if device_group_name not in current_group_names:
                            _LOGGER.info(
                                "Marking device for removal: %s (group '%s' no longer exists)",
                                device_entry.name,
                                device_group_name,
                            )
                            devices_to_remove.append(device_entry.id)
                            break
    
    # Remove devices and their entities
    for device_id in devices_to_remove:
        # First remove all entities for this device
        entities_to_remove = []
        for entity_entry in entity_registry.entities.values():
            if entity_entry.device_id == device_id:
                entities_to_remove.append(entity_entry.entity_id)
        
        for entity_id in entities_to_remove:
            _LOGGER.info("Removing entity: %s", entity_id)
            entity_registry.async_remove(entity_id)
        
        # Then remove the device
        _LOGGER.info("Removing device: %s", device_id)
        device_registry.async_remove_device(device_id)
    
    # Also check for orphaned entities without devices
    entities_to_remove = []
    for entity_id, entity_entry in entity_registry.entities.items():
        if (
            entity_entry.config_entry_id == config_entry_id
            and entity_entry.platform == DOMAIN
        ):
            # Check if the entity's unique_id matches any current group
            if entity_entry.unique_id and entity_entry.unique_id.startswith(f"{config_entry_id}_"):
                # Extract group name from unique_id
                # Format: "{config_entry_id}_{sanitized_group_name}_{sensor_type}"
                parts = entity_entry.unique_id.split("_", 2)
                if len(parts) >= 2:
                    entity_group_name = parts[1]
                    # Special handling for legacy sensors that might have different formats
                    if entity_group_name not in current_group_names and entity_group_name != config_entry_id:
                        # Check if this might be a multi-part group name
                        # Try to match progressively longer group names
                        found = False
                        for i in range(2, len(parts)):
                            potential_group = "_".join(parts[1:i])
                            if potential_group in current_group_names:
                                found = True
                                break
                        
                        if not found:
                            _LOGGER.info(
                                "Marking orphaned entity for removal: %s (group '%s' no longer exists)",
                                entity_id,
                                entity_group_name,
                            )
                            entities_to_remove.append(entity_id)
    
    for entity_id in entities_to_remove:
        _LOGGER.info("Removing orphaned entity: %s", entity_id)
        entity_registry.async_remove(entity_id)