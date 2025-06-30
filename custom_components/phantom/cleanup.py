"""Simple device cleanup for Phantom Power Monitoring."""
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


async def async_cleanup_orphaned_devices(
    hass: HomeAssistant,
    config_entry_id: str,
    config: dict[str, Any],
) -> None:
    """Remove devices that no longer exist in the config."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    
    # Get current group names from config
    current_groups = set()
    if CONF_GROUPS in config:
        for group in config.get(CONF_GROUPS, []):
            group_name = group.get(CONF_GROUP_NAME, "")
            if group_name:
                # Store the sanitized name that matches device identifiers
                current_groups.add(_sanitize_name(group_name))
    
    _LOGGER.info("Current groups in config: %s", current_groups)
    
    # Find all devices for this config entry
    devices_to_remove = []
    for device_entry in device_registry.devices.values():
        # Check if this device belongs to our config entry
        if config_entry_id in device_entry.config_entries:
            # Check identifiers
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN:
                    # Identifier format: (DOMAIN, "{config_entry_id}_{sanitized_group_name}")
                    device_id_parts = identifier[1].split("_", 1)
                    if len(device_id_parts) == 2 and device_id_parts[0] == config_entry_id:
                        device_group = device_id_parts[1]
                        
                        # If this group is not in current config, mark for removal
                        if device_group not in current_groups:
                            _LOGGER.info(
                                "Device '%s' belongs to group '%s' which no longer exists",
                                device_entry.name,
                                device_group
                            )
                            devices_to_remove.append(device_entry.id)
                            break
    
    # Remove devices and their entities
    for device_id in devices_to_remove:
        device = device_registry.async_get(device_id)
        if device:
            # Count entities
            entity_count = sum(
                1 for e in entity_registry.entities.values()
                if e.device_id == device_id
            )
            
            _LOGGER.info(
                "Removing device '%s' with %d entities",
                device.name,
                entity_count
            )
            
            # Remove the device (this also removes all its entities)
            device_registry.async_remove_device(device_id)