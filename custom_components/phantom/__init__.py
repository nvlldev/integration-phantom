"""The Phantom Power Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .api import async_setup_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Phantom Power Monitoring component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Phantom Power Monitoring from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Merge entry.data with entry.options, with options taking precedence
    config = {**entry.data}
    if entry.options:
        config.update(entry.options)
    
    hass.data[DOMAIN][entry.entry_id] = config

    # Create device registry entry
    device_registry = dr.async_get(hass)
    
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Phantom",
        model="Power Monitor",
        sw_version="1.0.0",
    )

    # Set up API
    async_setup_api(hass)
    
    # Register custom panel
    await _async_register_panel(hass)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Add options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the Phantom configuration panel."""
    # Register static path for panel files
    panel_dir = hass.config.path("custom_components/phantom/panel")
    hass.http.register_static_path(
        "/phantom-static", 
        panel_dir,
        True
    )
    _LOGGER.info("Registered static path for panel files: %s -> /phantom-static", panel_dir)
    
    try:
        # Import and use the frontend's panel registration
        from homeassistant.components import frontend
        
        # This is the direct approach used by core integrations
        hass.data.setdefault(frontend.DATA_PANELS, {})
        
        # Register the panel data
        hass.data[frontend.DATA_PANELS]["phantom"] = {
            "component_name": "custom",
            "sidebar_title": "Phantom",
            "sidebar_icon": "mdi:flash",
            "frontend_url_path": "phantom",
            "config": {"js_url": "/phantom-static/phantom-panel.js"},
            "require_admin": True,
        }
        
        # Trigger frontend to refresh panels
        hass.bus.async_fire("panels_updated")
        
        _LOGGER.info("Phantom panel registered automatically in sidebar")
        
    except Exception as err:
        _LOGGER.error("Failed to auto-register panel: %s", err)
        
        # Fallback: Try to use the panel_custom integration if available
        try:
            if "panel_custom" in hass.config.components:
                # Load the panel_custom platform programmatically
                config_data = {
                    "panel_custom": [
                        {
                            "name": "phantom-panel",
                            "sidebar_title": "Phantom",
                            "sidebar_icon": "mdi:flash",
                            "url_path": "phantom",
                            "module_url": "/phantom-static/phantom-panel.js",
                            "require_admin": True,
                        }
                    ]
                }
                
                # Import and set up panel_custom
                from homeassistant.components import panel_custom
                await panel_custom.async_setup(hass, config_data)
                
                _LOGGER.info("Phantom panel registered via panel_custom")
                
            else:
                _LOGGER.warning("panel_custom not available. Manual configuration needed:")
                _LOGGER.warning("Add to configuration.yaml:")
                _LOGGER.warning("panel_custom:")
                _LOGGER.warning("  - name: phantom-panel")
                _LOGGER.warning("    sidebar_title: Phantom") 
                _LOGGER.warning("    sidebar_icon: mdi:flash")
                _LOGGER.warning("    url_path: phantom")
                _LOGGER.warning("    module_url: /phantom-static/phantom-panel.js")
                
        except Exception as fallback_err:
            _LOGGER.error("Fallback panel registration also failed: %s", fallback_err)
            _LOGGER.warning("Manual configuration required - see logs above")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)