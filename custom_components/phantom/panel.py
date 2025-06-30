"""Panel registration for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the Phantom configuration panel."""
    # Register static path for panel files
    panel_dir = hass.config.path("custom_components/phantom/panel")
    hass.http.register_static_path(
        "/phantom-static", 
        panel_dir,
        True
    )
    _LOGGER.info("Registered static path for panel files: %s -> /phantom-static", panel_dir)
    
    # Check if panel already exists
    frontend_panels = getattr(hass.components.frontend, "panels", {})
    if "phantom" in frontend_panels:
        _LOGGER.info("Phantom panel already registered, skipping registration")
        return
    
    try:
        # Register the panel using the proper method
        frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="Phantom",
            sidebar_icon="mdi:flash",
            frontend_url_path="phantom",
            config={
                "name": "ha-panel-phantom",
                "embed_iframe": False,
                "trust_external": False,
                "js_url": "/phantom-static/ha-panel-phantom.js",
            },
            require_admin=True,
        )
        
        _LOGGER.info("✅ Phantom panel registered successfully")
    except ValueError as e:
        if "Overwriting panel" in str(e):
            _LOGGER.warning("Panel already exists, this is expected on reload")
        else:
            raise