"""The Phantom Power Monitoring integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import async_setup_api
from .const import DOMAIN
from .panel import async_register_panel
from .cleanup import async_cleanup_orphaned_devices

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
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
    
    _LOGGER.info("Loading Phantom config for entry %s: %s", entry.entry_id, config)
    hass.data[DOMAIN][entry.entry_id] = config

    # Set up API
    async_setup_api(hass)
    
    # Register custom panel
    await async_register_panel(hass)
    
    # Clean up orphaned devices before setting up new ones
    await async_cleanup_orphaned_devices(hass, entry.entry_id, config)
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Don't add update listener - we'll handle reloads manually
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)