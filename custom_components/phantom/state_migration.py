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
    """Create a mapping of old entity IDs to new entity IDs for renamed groups."""
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
                    if device_name and device.get("energy_entity"):
                        old_unique_id = f"{config_entry_id}_{_sanitize_name(old_name)}_utility_meter_{_sanitize_name(device_name)}"
                        new_unique_id = f"{config_entry_id}_{_sanitize_name(new_name)}_utility_meter_{_sanitize_name(device_name)}"
                        
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
                old_upstream_id = f"{config_entry_id}_{_sanitize_name(old_name)}_upstream_energy_meter"
                new_upstream_id = f"{config_entry_id}_{_sanitize_name(new_name)}_upstream_energy_meter"
                
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
    
    return migration_mapping


def _groups_have_same_devices(devices1: list[dict], devices2: list[dict]) -> bool:
    """Check if two device lists contain the same devices."""
    if len(devices1) != len(devices2):
        return False
    
    # Create sets of device configurations for comparison
    dev1_set = {
        (dev.get("name", ""), dev.get("power_entity", ""), dev.get("energy_entity", ""))
        for dev in devices1
    }
    
    dev2_set = {
        (dev.get("name", ""), dev.get("power_entity", ""), dev.get("energy_entity", ""))
        for dev in devices2
    }
    
    return dev1_set == dev2_set


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