"""Phantom panel registration."""
import logging
from typing import Any

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

URL_PANEL = "/phantom_panel"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Phantom configuration panel."""
    _LOGGER.info("Registering Phantom panel...")
    
    # Register static path for panel files
    panel_dir = hass.config.path("custom_components/phantom/panel")
    hass.http.register_static_path(
        URL_PANEL, 
        panel_dir,
        False  # Don't cache during development
    )
    
    # Register the panel
    await async_register_built_in_panel(
        hass,
        component_name="config",  # Use "config" not "custom"
        sidebar_title="Phantom",
        sidebar_icon="mdi:flash",
        frontend_url_path="phantom",
        config={
            "_panel_custom": {
                "name": "phantom-panel",
                "embed_iframe": False,
                "trust_external": False,
                "js_url": f"{URL_PANEL}/phantom-panel.js",
            }
        },
        require_admin=True,
    )
    
    _LOGGER.info("Phantom panel registered successfully")