"""The Phantom Power Monitoring integration."""
from __future__ import annotations

import asyncio
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
    
    # Wait a moment for other components to load
    await asyncio.sleep(1)
    
    try:
        # Method 1: Direct service call to register panel
        _LOGGER.info("Attempting to register panel via service call...")
        
        await hass.services.async_call(
            "frontend",
            "register_panel",
            {
                "panel_name": "phantom",
                "sidebar_title": "Phantom",
                "sidebar_icon": "mdi:flash",
                "url_path": "phantom",
                "js_url": "/phantom-static/phantom-panel.js",
                "require_admin": True,
            },
            blocking=True,
        )
        
        _LOGGER.info("✅ Panel registered successfully via service call")
        return
        
    except Exception as err:
        _LOGGER.warning("Service call registration failed: %s", err)
    
    try:
        # Method 2: Use the low-level frontend approach
        _LOGGER.info("Attempting direct frontend registration...")
        
        from homeassistant.components.frontend import async_register_built_in_panel
        
        await async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="Phantom",
            sidebar_icon="mdi:flash",
            frontend_url_path="phantom",
            config={"js_url": "/phantom-static/phantom-panel.js"},
            require_admin=True,
        )
        
        _LOGGER.info("✅ Panel registered successfully via frontend API")
        return
        
    except Exception as err:
        _LOGGER.warning("Frontend API registration failed: %s", err)
    
    try:
        # Method 3: Manual panel_custom setup
        _LOGGER.info("Attempting panel_custom programmatic setup...")
        
        # Create a fake config entry for panel_custom
        from homeassistant.config_entries import ConfigEntry
        from homeassistant.const import CONF_NAME
        
        # Set up panel_custom if not already set up
        if "panel_custom" not in hass.config.components:
            hass.config.components.add("panel_custom")
        
        # Register directly with panel_custom's internal method
        hass.data.setdefault("panel_custom_panels", {})
        hass.data["panel_custom_panels"]["phantom"] = {
            "name": "phantom-panel",
            "sidebar_title": "Phantom",
            "sidebar_icon": "mdi:flash",
            "url_path": "phantom",
            "js_url": "/phantom-static/phantom-panel.js",
            "require_admin": True,
        }
        
        # Fire an event to notify frontend
        hass.bus.async_fire("panel_custom_updated")
        
        _LOGGER.info("✅ Panel registered via panel_custom data")
        return
        
    except Exception as err:
        _LOGGER.warning("panel_custom registration failed: %s", err)
    
    # All methods failed
    _LOGGER.error("❌ All automatic registration methods failed!")
    _LOGGER.error("MANUAL SETUP REQUIRED:")
    _LOGGER.error("Add this to your configuration.yaml:")
    _LOGGER.error("")
    _LOGGER.error("panel_custom:")
    _LOGGER.error("  - name: phantom-panel")
    _LOGGER.error("    sidebar_title: Phantom")
    _LOGGER.error("    sidebar_icon: mdi:flash")
    _LOGGER.error("    url_path: phantom")
    _LOGGER.error("    module_url: /phantom-static/phantom-panel.js")
    _LOGGER.error("")
    _LOGGER.error("Then restart Home Assistant.")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)