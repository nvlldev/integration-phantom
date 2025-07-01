"""State migration for preserving utility meter values.

With UUID-based unique IDs, this is now mainly for backward compatibility
and major configuration changes rather than simple renames.
"""
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
    """Create a mapping for migrating entities to UUID-based unique IDs.
    
    With UUID-based unique IDs, renames no longer require migration.
    This function now mainly handles migration from old format to new UUID format.
    """
    migration_mapping = {}
    
    # Log that we're checking for migrations
    _LOGGER.info("Checking for entity migrations (UUID-based system)")
    
    # With UUIDs, entities maintain their identity across renames
    # Migration is only needed when transitioning from old format to new
    # or for major structural changes
    
    return migration_mapping






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