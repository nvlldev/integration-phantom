"""Helper functions for entity operations."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_DEVICE_ID
from .utils import sanitize_name

_LOGGER = logging.getLogger(__name__)


def find_entity_by_unique_id(
    hass: HomeAssistant,
    unique_id: str,
    platform: str = DOMAIN,
) -> str | None:
    """Find entity ID by unique ID."""
    entity_registry = er.async_get(hass)
    
    for entity_id, entry in entity_registry.entities.items():
        if (
            entry.unique_id == unique_id
            and entry.platform == platform
            and entry.domain == "sensor"
        ):
            return entity_id
    
    return None


def find_utility_meter_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    group_name: str,
    devices: list[dict[str, Any]],
) -> list[str]:
    """Find utility meter entities for devices."""
    entity_registry = er.async_get(hass)
    utility_meters = []
    
    for device in devices:
        device_id = device.get(CONF_DEVICE_ID)
        
        if device_id:
            # New UUID-based unique ID format
            expected_unique_id = f"{device_id}_utility_meter"
        else:
            # Fallback to old format if no UUID (shouldn't happen)
            device_name = device.get("name", "Unknown")
            expected_unique_id = f"{config_entry_id}_{sanitize_name(group_name)}_utility_meter_{sanitize_name(device_name)}"
        
        # Find entity with this unique ID
        entity_id = find_entity_by_unique_id(hass, expected_unique_id)
        if entity_id:
            utility_meters.append(entity_id)
    
    return utility_meters