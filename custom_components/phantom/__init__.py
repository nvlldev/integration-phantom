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
from .panel import async_register_panel

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
    await async_register_panel(hass)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Add options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
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