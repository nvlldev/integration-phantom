"""State migration for preserving utility meter values during renames."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_GROUPS, CONF_GROUP_NAME, CONF_DEVICES, CONF_DEVICE_ID
from .utils import sanitize_name

_LOGGER = logging.getLogger(__name__)

# Storage key for migration data
MIGRATION_STORAGE_KEY = f"{DOMAIN}_state_migration"




def save_current_states_for_migration(
    hass: HomeAssistant,
    config_entry_id: str,
) -> dict[str, Any]:
    """Save all current utility meter states and their entity IDs."""
    saved_states = {}
    entity_registry = er.async_get(hass)
    
    # Find all phantom utility meter entities for this config entry
    for entity_id, entry in entity_registry.entities.items():
        if (entry.platform == DOMAIN and 
            entry.config_entry_id == config_entry_id and
            ("utility_meter" in entry.unique_id or "energy_meter" in entry.unique_id)):
            
            state = hass.states.get(entity_id)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                # Store state with both entity_id and unique_id for easy lookup
                saved_states[entity_id] = {
                    "state": state.state,
                    "attributes": dict(state.attributes),
                    "unique_id": entry.unique_id,
                }
                _LOGGER.debug(
                    "Saved state for %s (unique_id: %s): %s",
                    entity_id,
                    entry.unique_id,
                    state.state
                )
    
    _LOGGER.info("Saved %d utility meter states for potential migration", len(saved_states))
    return saved_states


def create_migration_mapping(
    old_config: dict[str, Any],
    new_config: dict[str, Any],
    config_entry_id: str,
    saved_states: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Create a mapping of old entity IDs to new entity IDs for renamed groups and devices."""
    migration_mapping = {}
    
    # Get groups from configs
    old_groups = {group.get(CONF_GROUP_NAME): group for group in old_config.get(CONF_GROUPS, [])}
    new_groups = {group.get(CONF_GROUP_NAME): group for group in new_config.get(CONF_GROUPS, [])}
    
    # Find renamed groups by comparing device configurations
    for old_name, old_group in old_groups.items():
        for new_name, new_group in new_groups.items():
            if old_name != new_name and _groups_have_same_devices(
                old_group.get(CONF_DEVICES, []), 
                new_group.get(CONF_DEVICES, [])
            ):
                _LOGGER.info("Detected group rename: '%s' -> '%s'", old_name, new_name)
                
                # Create mappings for all utility meters in this group
                for device in old_group.get(CONF_DEVICES, []):
                    device_name = device.get("name", "")
                    device_id = device.get(CONF_DEVICE_ID)
                    
                    if device_id and device.get("energy_entity"):
                        # Use device ID for unique ID if available
                        old_unique_id = f"{config_entry_id}_{sanitize_name(old_name)}_utility_meter_{device_id}"
                        new_unique_id = f"{config_entry_id}_{sanitize_name(new_name)}_utility_meter_{device_id}"
                    elif device_name and device.get("energy_entity"):
                        # Fallback to device name if no ID (shouldn't happen with new code)
                        old_unique_id = f"{config_entry_id}_{sanitize_name(old_name)}_utility_meter_{sanitize_name(device_name)}"
                        new_unique_id = f"{config_entry_id}_{sanitize_name(new_name)}_utility_meter_{sanitize_name(device_name)}"
                    else:
                        continue
                        
                    # Find the old entity ID from saved states
                    for entity_id, state_data in saved_states.items():
                        if state_data["unique_id"] == old_unique_id:
                            migration_mapping[old_unique_id] = {
                                "old_entity_id": entity_id,
                                "new_unique_id": new_unique_id,
                                "state": state_data["state"],
                                "attributes": state_data["attributes"],
                            }
                            _LOGGER.debug(
                                "Migration mapping: %s -> %s (state: %s)",
                                entity_id,
                                new_unique_id,
                                state_data["state"]
                            )
                            break
                
                # Map upstream energy meter if it exists
                old_upstream_id = f"{config_entry_id}_{sanitize_name(old_name)}_upstream_energy_meter"
                new_upstream_id = f"{config_entry_id}_{sanitize_name(new_name)}_upstream_energy_meter"
                
                for entity_id, state_data in saved_states.items():
                    if state_data["unique_id"] == old_upstream_id:
                        migration_mapping[old_upstream_id] = {
                            "old_entity_id": entity_id,
                            "new_unique_id": new_upstream_id,
                            "state": state_data["state"],
                            "attributes": state_data["attributes"],
                        }
                        _LOGGER.debug(
                            "Migration mapping (upstream): %s -> %s (state: %s)",
                            entity_id,
                            new_upstream_id,
                            state_data["state"]
                        )
                        break
    
    # Check for device renames within the same group using UUIDs
    for group_name in old_groups:
        if group_name in new_groups:
            old_devices = old_groups[group_name].get(CONF_DEVICES, [])
            new_devices = new_groups[group_name].get(CONF_DEVICES, [])
            
            # Create lookup by device ID
            old_devices_by_id = {
                dev.get(CONF_DEVICE_ID): dev 
                for dev in old_devices 
                if dev.get(CONF_DEVICE_ID)
            }
            new_devices_by_id = {
                dev.get(CONF_DEVICE_ID): dev 
                for dev in new_devices 
                if dev.get(CONF_DEVICE_ID)
            }
            
            # Find devices with same ID but different names
            for device_id, old_device in old_devices_by_id.items():
                if device_id in new_devices_by_id:
                    new_device = new_devices_by_id[device_id]
                    old_name = old_device.get("name", "")
                    new_name = new_device.get("name", "")
                    
                    if old_name != new_name and old_name and new_name:
                        _LOGGER.info("Detected device rename in group '%s': '%s' -> '%s' (ID: %s)", 
                                   group_name, old_name, new_name, device_id)
                        
                        # Create mapping for utility meter using device ID
                        old_unique_id = f"{config_entry_id}_{sanitize_name(group_name)}_utility_meter_{device_id}"
                        new_unique_id = old_unique_id  # Same unique ID since we're using device ID
                        
                        # No migration needed since unique ID doesn't change!
                        _LOGGER.debug(
                            "Device '%s' renamed to '%s' - no migration needed (UUID-based unique ID)",
                            old_name,
                            new_name
                        )
    
    return migration_mapping


def _groups_have_same_devices(devices1: list[dict], devices2: list[dict]) -> bool:
    """Check if two device lists contain the same devices."""
    if len(devices1) != len(devices2):
        return False
    
    # If all devices have IDs, compare by ID
    all_have_ids = all(dev.get(CONF_DEVICE_ID) for dev in devices1 + devices2)
    if all_have_ids:
        ids1 = {dev.get(CONF_DEVICE_ID) for dev in devices1}
        ids2 = {dev.get(CONF_DEVICE_ID) for dev in devices2}
        return ids1 == ids2
    
    # Otherwise, fall back to entity comparison
    dev1_set = {
        (dev.get("power_entity", ""), dev.get("energy_entity", ""))
        for dev in devices1
    }
    
    dev2_set = {
        (dev.get("power_entity", ""), dev.get("energy_entity", ""))
        for dev in devices2
    }
    
    return dev1_set == dev2_set


def _find_renamed_devices(old_devices: list[dict], new_devices: list[dict]) -> dict[str, str]:
    """Find devices that have been renamed by comparing entity IDs."""
    device_mappings = {}
    
    # Create lookups by entity IDs
    old_by_entities = {
        (dev.get("power_entity", ""), dev.get("energy_entity", "")): dev.get("name", "")
        for dev in old_devices
        if dev.get("power_entity") or dev.get("energy_entity")
    }
    
    new_by_entities = {
        (dev.get("power_entity", ""), dev.get("energy_entity", "")): dev.get("name", "")
        for dev in new_devices
        if dev.get("power_entity") or dev.get("energy_entity")
    }
    
    # Find devices with same entity IDs but different names
    for entity_pair, old_name in old_by_entities.items():
        if entity_pair in new_by_entities:
            new_name = new_by_entities[entity_pair]
            if old_name != new_name:
                device_mappings[old_name] = new_name
    
    return device_mappings


def store_migration_data(
    hass: HomeAssistant,
    config_entry_id: str,
    migration_mapping: dict[str, dict[str, Any]],
) -> None:
    """Store migration data in hass.data."""
    if MIGRATION_STORAGE_KEY not in hass.data:
        hass.data[MIGRATION_STORAGE_KEY] = {}
    
    # Convert to lookup by new unique ID for easier access during restore
    migration_by_new_id = {}
    for old_unique_id, mapping in migration_mapping.items():
        new_unique_id = mapping["new_unique_id"]
        migration_by_new_id[new_unique_id] = {
            "state": mapping["state"],
            "attributes": mapping["attributes"],
            "old_entity_id": mapping["old_entity_id"],
        }
    
    hass.data[MIGRATION_STORAGE_KEY][config_entry_id] = migration_by_new_id
    _LOGGER.info("Stored migration data for %d entities", len(migration_by_new_id))


def get_migrated_state(hass: HomeAssistant, config_entry_id: str, unique_id: str) -> dict[str, Any] | None:
    """Get migrated state for an entity."""
    migration_data = hass.data.get(MIGRATION_STORAGE_KEY, {}).get(config_entry_id, {})
    return migration_data.get(unique_id)


def clear_migration_data(hass: HomeAssistant, config_entry_id: str) -> None:
    """Clear migration data after successful migration."""
    if MIGRATION_STORAGE_KEY in hass.data and config_entry_id in hass.data[MIGRATION_STORAGE_KEY]:
        del hass.data[MIGRATION_STORAGE_KEY][config_entry_id]
        _LOGGER.debug("Cleared migration data for config entry %s", config_entry_id)