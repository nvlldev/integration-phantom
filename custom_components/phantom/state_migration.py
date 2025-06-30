"""State migration for preserving utility meter values during renames."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_GROUPS, CONF_GROUP_NAME, CONF_DEVICES

_LOGGER = logging.getLogger(__name__)

# Storage key for migration data
MIGRATION_STORAGE_KEY = f"{DOMAIN}_state_migration"


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use in entity IDs."""
    return name.lower().replace(" ", "_").replace("-", "_")


async def async_save_states_before_reload(
    hass: HomeAssistant,
    config_entry_id: str,
    old_config: dict[str, Any],
    new_config: dict[str, Any],
) -> None:
    """Save utility meter states before reload for migration."""
    entity_registry = er.async_get(hass)
    
    # Initialize storage
    if MIGRATION_STORAGE_KEY not in hass.data:
        hass.data[MIGRATION_STORAGE_KEY] = {}
    
    migration_data = {}
    
    # Compare old and new configs to find renamed groups
    old_groups = {}
    new_groups = {}
    
    # Build old groups map
    if CONF_GROUPS in old_config:
        for idx, group in enumerate(old_config[CONF_GROUPS]):
            group_name = group.get(CONF_GROUP_NAME, "")
            if group_name:
                old_groups[idx] = {
                    "name": group_name,
                    "devices": group.get(CONF_DEVICES, [])
                }
                _LOGGER.debug(f"Old group {idx}: {group_name}")
    
    # Build new groups map
    if CONF_GROUPS in new_config:
        for idx, group in enumerate(new_config[CONF_GROUPS]):
            group_name = group.get(CONF_GROUP_NAME, "")
            if group_name:
                new_groups[idx] = {
                    "name": group_name,
                    "devices": group.get(CONF_DEVICES, [])
                }
                _LOGGER.debug(f"New group {idx}: {group_name}")
    
    # Find renamed groups by comparing device configurations
    _LOGGER.debug(f"Comparing {len(old_groups)} old groups with {len(new_groups)} new groups")
    for old_idx, old_group in old_groups.items():
        for new_idx, new_group in new_groups.items():
            # Check if groups have the same devices (indicating a rename)
            same_devices = _groups_have_same_devices(old_group["devices"], new_group["devices"])
            _LOGGER.debug(f"Comparing '{old_group['name']}' with '{new_group['name']}': same_devices={same_devices}")
            if (old_group["name"] != new_group["name"] and same_devices):
                
                _LOGGER.info(
                    "Detected group rename: '%s' -> '%s'",
                    old_group["name"],
                    new_group["name"]
                )
                
                # Save states for this group's entities
                await _save_group_states(
                    hass,
                    config_entry_id,
                    old_group["name"],
                    new_group["name"],
                    old_group["devices"],
                    migration_data
                )
    
    # Store migration data
    if migration_data:
        hass.data[MIGRATION_STORAGE_KEY][config_entry_id] = migration_data
        _LOGGER.info("Saved %d entity states for migration", len(migration_data))


def _groups_have_same_devices(devices1: list[dict], devices2: list[dict]) -> bool:
    """Check if two device lists contain the same devices."""
    if len(devices1) != len(devices2):
        return False
    
    # Create sets of device configurations for comparison
    dev1_set = set()
    for dev in devices1:
        # Use tuple of relevant fields for comparison
        dev1_set.add((
            dev.get("name", ""),
            dev.get("power_entity", ""),
            dev.get("energy_entity", "")
        ))
    
    dev2_set = set()
    for dev in devices2:
        dev2_set.add((
            dev.get("name", ""),
            dev.get("power_entity", ""),
            dev.get("energy_entity", "")
        ))
    
    return dev1_set == dev2_set


async def _save_group_states(
    hass: HomeAssistant,
    config_entry_id: str,
    old_group_name: str,
    new_group_name: str,
    devices: list[dict],
    migration_data: dict[str, Any],
) -> None:
    """Save states for a group's entities."""
    # Save utility meter states
    for device in devices:
        device_name = device.get("name", "")
        if device_name and device.get("energy_entity"):
            # Old unique ID
            old_unique_id = f"{config_entry_id}_{_sanitize_name(old_group_name)}_utility_meter_{_sanitize_name(device_name)}"
            # New unique ID
            new_unique_id = f"{config_entry_id}_{_sanitize_name(new_group_name)}_utility_meter_{_sanitize_name(device_name)}"
            
            # Find entity by unique ID
            entity_id = None
            entity_registry = er.async_get(hass)
            for ent_id, entry in entity_registry.entities.items():
                if entry.unique_id == old_unique_id and entry.platform == DOMAIN:
                    entity_id = ent_id
                    break
            
            if entity_id:
                state = hass.states.get(entity_id)
                if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    migration_data[new_unique_id] = {
                        "state": state.state,
                        "attributes": dict(state.attributes),
                        "old_entity_id": entity_id,
                    }
                    _LOGGER.debug(
                        "Saved state for %s: %s -> %s",
                        device_name,
                        old_unique_id,
                        new_unique_id
                    )
    
    # Save upstream energy meter state
    old_upstream_id = f"{config_entry_id}_{_sanitize_name(old_group_name)}_upstream_energy_meter"
    new_upstream_id = f"{config_entry_id}_{_sanitize_name(new_group_name)}_upstream_energy_meter"
    
    # Find upstream entity
    entity_registry = er.async_get(hass)
    for entity_id, entry in entity_registry.entities.items():
        if entry.unique_id == old_upstream_id and entry.platform == DOMAIN:
            state = hass.states.get(entity_id)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                migration_data[new_upstream_id] = {
                    "state": state.state,
                    "attributes": dict(state.attributes),
                    "old_entity_id": entity_id,
                }
                _LOGGER.debug("Saved upstream energy meter state")
            break


def get_migrated_state(hass: HomeAssistant, config_entry_id: str, unique_id: str) -> dict[str, Any] | None:
    """Get migrated state for an entity."""
    migration_data = hass.data.get(MIGRATION_STORAGE_KEY, {}).get(config_entry_id, {})
    return migration_data.get(unique_id)


def clear_migration_data(hass: HomeAssistant, config_entry_id: str) -> None:
    """Clear migration data after successful migration."""
    if MIGRATION_STORAGE_KEY in hass.data and config_entry_id in hass.data[MIGRATION_STORAGE_KEY]:
        del hass.data[MIGRATION_STORAGE_KEY][config_entry_id]
        _LOGGER.debug("Cleared migration data for config entry %s", config_entry_id)