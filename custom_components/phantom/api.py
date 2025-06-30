"""API for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICES, CONF_UPSTREAM_POWER_ENTITY, CONF_UPSTREAM_ENERGY_ENTITY, DOMAIN

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
    
    result = {
        "devices": config.get(CONF_DEVICES, []),
        "upstream_power_entity": config.get(CONF_UPSTREAM_POWER_ENTITY),
        "upstream_energy_entity": config.get(CONF_UPSTREAM_ENERGY_ENTITY),
    }
    
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "phantom/save_config",
        vol.Required("devices"): [
            {
                vol.Required("name"): str,
                vol.Optional("power_entity", default=None): vol.Any(str, None),
                vol.Optional("energy_entity", default=None): vol.Any(str, None),
            }
        ],
        vol.Optional("upstream_power_entity", default=None): vol.Any(str, None),
        vol.Optional("upstream_energy_entity", default=None): vol.Any(str, None),
    }
)
@callback
def ws_save_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Save Phantom configuration."""
    # Find the Phantom config entry
    config_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        config_entry = entry
        break
    
    if not config_entry:
        connection.send_error(msg["id"], "not_found", "Phantom integration not found")
        return
    
    # Validate devices
    devices = msg["devices"]
    valid_devices = []
    
    for device in devices:
        name = device.get("name", "").strip()
        power_entity = device.get("power_entity") or None
        energy_entity = device.get("energy_entity") or None
        
        # Skip devices without name or sensors
        if not name or (not power_entity and not energy_entity):
            continue
            
        # Clean up empty strings
        if power_entity == "":
            power_entity = None
        if energy_entity == "":
            energy_entity = None
            
        valid_devices.append({
            "name": name,
            "power_entity": power_entity,
            "energy_entity": energy_entity,
        })
    
    # Prepare new configuration
    new_data = {
        CONF_DEVICES: valid_devices,
        CONF_UPSTREAM_POWER_ENTITY: msg.get("upstream_power_entity") or None,
        CONF_UPSTREAM_ENERGY_ENTITY: msg.get("upstream_energy_entity") or None,
    }
    
    # Clean up empty strings
    if new_data[CONF_UPSTREAM_POWER_ENTITY] == "":
        new_data[CONF_UPSTREAM_POWER_ENTITY] = None
    if new_data[CONF_UPSTREAM_ENERGY_ENTITY] == "":
        new_data[CONF_UPSTREAM_ENERGY_ENTITY] = None
    
    # Update config entry
    hass.config_entries.async_update_entry(config_entry, data=new_data)
    
    # Update runtime data
    hass.data[DOMAIN][config_entry.entry_id] = new_data
    
    _LOGGER.info("Phantom configuration updated: %d devices configured", len(valid_devices))
    
    connection.send_result(msg["id"], {"success": True})