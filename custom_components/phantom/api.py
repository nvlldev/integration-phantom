"""API for Phantom Power Monitoring."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_DEVICES, CONF_UPSTREAM_POWER_ENTITY, CONF_UPSTREAM_ENERGY_ENTITY, 
    CONF_GROUPS, CONF_GROUP_NAME, CONF_GROUP_ID, CONF_DEVICE_ID, DOMAIN,
    CONF_TARIFF, CONF_TARIFF_ENABLED, CONF_TARIFF_CURRENCY, CONF_TARIFF_CURRENCY_SYMBOL,
    CONF_TARIFF_RATE_STRUCTURE, CONF_TARIFF_RATE_TYPE, CONF_TARIFF_FLAT_RATE,
    CONF_TARIFF_TOU_RATES, CONF_TOU_NAME, CONF_TOU_RATE, CONF_TOU_START_TIME,
    CONF_TOU_END_TIME, CONF_TOU_DAYS, CONF_TARIFF_RATE_ENTITY, CONF_TARIFF_PERIOD_ENTITY
)
from .state_migration import save_current_states_for_migration, create_migration_mapping, store_migration_data

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_api(hass: HomeAssistant) -> None:
    """Set up the API for Phantom Power Monitoring."""
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_config)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "phantom/get_config",
    }
)
@callback
def ws_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get Phantom configuration."""
    # Find the Phantom config entry
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        config_entry = entry
        break
    
    if not config_entry:
        connection.send_error(msg["id"], "not_found", "Phantom integration not found")
        return
    
    # Get current configuration
    config = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
    
    # Return groups configuration and global tariff
    result = {
        "groups": config.get(CONF_GROUPS, []),
        "tariff": config.get(CONF_TARIFF)
    }
    
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "phantom/save_config",
        vol.Required("groups"): [
            {
                vol.Optional(CONF_GROUP_ID): str,
                vol.Required(CONF_GROUP_NAME): str,
                vol.Required(CONF_DEVICES): [
                    {
                        vol.Optional(CONF_DEVICE_ID): str,
                        vol.Required("name"): str,
                        vol.Optional("power_entity", default=None): vol.Any(str, None),
                        vol.Optional("energy_entity", default=None): vol.Any(str, None),
                    }
                ],
                vol.Optional(CONF_UPSTREAM_POWER_ENTITY, default=None): vol.Any(str, None),
                vol.Optional(CONF_UPSTREAM_ENERGY_ENTITY, default=None): vol.Any(str, None),
            }
        ],
        vol.Optional("tariff"): vol.Any(dict, None),
    }
)
@callback
def ws_save_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Save Phantom configuration."""
    _LOGGER.debug("Received save_config request with groups")
    
    # Find the Phantom config entry
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        config_entry = entry
        break
    
    if not config_entry:
        connection.send_error(msg["id"], "not_found", "Phantom integration not found")
        return
    
    # Validate groups
    groups = msg["groups"]
    valid_groups = []
    
    _LOGGER.debug("Validating %d groups", len(groups))
    
    for group in groups:
        group_name = group.get(CONF_GROUP_NAME, "").strip()
        group_id = group.get(CONF_GROUP_ID)
        
        if not group_name:
            _LOGGER.debug("Skipping group with empty name")
            continue
        
        # Generate UUID if not present
        if not group_id:
            group_id = str(uuid.uuid4())
            _LOGGER.info("Generated new UUID for group '%s': %s", group_name, group_id)
            
        # Validate devices in group
        devices = group.get(CONF_DEVICES, [])
        valid_devices = []
        
        _LOGGER.debug("Group '%s' has %d devices", group_name, len(devices))
        
        for device in devices:
            name = device.get("name", "").strip()
            power_entity = device.get("power_entity") or None
            energy_entity = device.get("energy_entity") or None
            device_id = device.get(CONF_DEVICE_ID)
            
            # Clean up empty strings
            if power_entity == "":
                power_entity = None
            if energy_entity == "":
                energy_entity = None
            
            # Skip devices without name
            if not name:
                _LOGGER.debug("Skipping device with empty name")
                continue
            
            # Skip devices without any sensors
            if not power_entity and not energy_entity:
                _LOGGER.debug("Skipping device '%s' - no sensors configured", name)
                continue
            
            # Generate UUID if not present
            if not device_id:
                device_id = str(uuid.uuid4())
                _LOGGER.info("Generated new UUID for device '%s': %s", name, device_id)
                
            valid_devices.append({
                CONF_DEVICE_ID: device_id,
                "name": name,
                "power_entity": power_entity,
                "energy_entity": energy_entity,
            })
            _LOGGER.debug(
                "Added device '%s' with power=%s, energy=%s",
                name,
                power_entity,
                energy_entity
            )
        
        # Clean up upstream entities
        upstream_power = group.get(CONF_UPSTREAM_POWER_ENTITY) or None
        upstream_energy = group.get(CONF_UPSTREAM_ENERGY_ENTITY) or None
        
        if upstream_power == "":
            upstream_power = None
        if upstream_energy == "":
            upstream_energy = None
        
        valid_groups.append({
            CONF_GROUP_ID: group_id,
            CONF_GROUP_NAME: group_name,
            CONF_DEVICES: valid_devices,
            CONF_UPSTREAM_POWER_ENTITY: upstream_power,
            CONF_UPSTREAM_ENERGY_ENTITY: upstream_energy,
        })
        
        _LOGGER.debug(
            "Group '%s' validated: %d devices, upstream_power=%s, upstream_energy=%s",
            group_name,
            len(valid_devices),
            upstream_power,
            upstream_energy
        )
    
    # Prepare new configuration
    new_data = {CONF_GROUPS: valid_groups}
    
    # Add tariff configuration if provided
    if "tariff" in msg and msg["tariff"]:
        new_data[CONF_TARIFF] = msg["tariff"]
    
    # Get old configuration before updating
    old_data = dict(hass.data[DOMAIN][config_entry.entry_id])
    
    # Save current states BEFORE any configuration changes
    _LOGGER.info("Saving current entity states before configuration update...")
    saved_states = save_current_states_for_migration(hass, config_entry.entry_id)
    
    # Create migration mapping for renamed groups
    migration_mapping = create_migration_mapping(old_data, new_data, config_entry.entry_id, saved_states)
    
    # Store migration data if any renames were detected
    if migration_mapping:
        store_migration_data(hass, config_entry.entry_id, migration_mapping)
        _LOGGER.info("Stored migration data for group renames")
    
    # Update config entry
    hass.config_entries.async_update_entry(config_entry, data=new_data)
    
    # Update runtime data
    hass.data[DOMAIN][config_entry.entry_id] = new_data
    
    _LOGGER.info("Phantom configuration updated: %d groups configured", len(valid_groups))
    for i, group in enumerate(valid_groups):
        _LOGGER.info(
            "  Group %d: '%s' with %d devices",
            i + 1,
            group[CONF_GROUP_NAME],
            len(group[CONF_DEVICES])
        )
    
    # Send success response
    connection.send_result(msg["id"], {"success": True})
    
    # Always reload to apply configuration changes
    _LOGGER.info("Configuration saved, reloading integration")
    hass.async_create_task(hass.config_entries.async_reload(config_entry.entry_id))