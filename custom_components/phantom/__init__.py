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
        "/local/phantom", 
        panel_dir,
        True
    )
    _LOGGER.info("Registered static path for panel files: %s -> /local/phantom", panel_dir)
    
    # Create a simple HTML wrapper that loads our component
    wrapper_html = """<!DOCTYPE html>
<html>
<head>
    <title>Phantom Power Monitoring</title>
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto; }
    </style>
</head>
<body>
    <phantom-panel></phantom-panel>
    <script type="module" src="/local/phantom/phantom-panel.js"></script>
    <script>
        // Wait for Home Assistant to load and pass hass object
        window.addEventListener('message', (event) => {
            if (event.data.type === 'hass-update') {
                const panel = document.querySelector('phantom-panel');
                if (panel) {
                    panel.hass = event.data.hass;
                }
            }
        });
        
        // Also try to get hass from window
        setTimeout(() => {
            const panel = document.querySelector('phantom-panel');
            if (panel && window.parent && window.parent.hass) {
                panel.hass = window.parent.hass;
            }
        }, 1000);
    </script>
</body>
</html>"""
    
    # Write the wrapper HTML file
    wrapper_path = hass.config.path("custom_components/phantom/panel/index.html")
    try:
        with open(wrapper_path, "w") as f:
            f.write(wrapper_html)
        _LOGGER.info("Created panel wrapper HTML at: %s", wrapper_path)
    except Exception as err:
        _LOGGER.error("Failed to create panel wrapper: %s", err)
    
    # Skip panel registration for now - user will need to add manually
    _LOGGER.info("Panel files ready. Add this to configuration.yaml:")
    _LOGGER.info("panel_custom:")
    _LOGGER.info("  - name: phantom-panel")
    _LOGGER.info("    sidebar_title: Phantom")
    _LOGGER.info("    sidebar_icon: mdi:flash")
    _LOGGER.info("    url_path: phantom")
    _LOGGER.info("    module_url: /local/phantom/phantom-panel.js")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)