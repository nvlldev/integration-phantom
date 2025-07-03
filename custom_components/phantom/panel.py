"""Panel registration for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig

_LOGGER = logging.getLogger(__name__)


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Phantom configuration panel."""
    # Register static path for panel files
    panel_dir = hass.config.path("custom_components/phantom/panel")
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path="/phantom-static",
            path=panel_dir,
            cache_headers=True
        )
    ])
    _LOGGER.info("Registered static path for panel files: %s -> /phantom-static", panel_dir)
    
    try:
        # Register the panel directly without checking
        # The frontend component handles duplicate registrations internally
        frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="Phantom",
            sidebar_icon="mdi:flash",
            frontend_url_path="phantom",
            config={
                "_panel_custom": {
                    "name": "phantom-config-panel",
                    "embed_iframe": False,
                    "trust_external": False,
                    "module_url": "/phantom-static/phantom-config-panel.js?v=9.0",
                }
            },
            require_admin=True,
            update=True,  # Allow updating existing panel
        )
        
        _LOGGER.info("✅ Phantom panel registered successfully")
    except Exception as e:
        _LOGGER.error("Failed to register panel: %s", e)
        # Don't raise - allow the integration to continue loading