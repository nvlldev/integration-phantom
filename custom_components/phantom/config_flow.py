"""Config flow for Phantom Power Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PhantomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phantom Power Monitoring."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        
        # Check if any instance already exists
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Create the entry immediately with empty groups
        return self.async_create_entry(
            title="Phantom Power Monitoring",
            data={"groups": []},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PhantomOptionsFlowHandler:
        """Create the options flow."""
        return PhantomOptionsFlowHandler(config_entry)


class PhantomOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Phantom Power Monitoring."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )