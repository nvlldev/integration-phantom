"""Config flow for Phantom Power Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    CONF_DEVICES,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    CONF_POWER_ENTITIES,
    CONF_ENERGY_ENTITIES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_power_entities(hass: HomeAssistant) -> dict[str, str]:
    """Get all power sensor entities with their friendly names."""
    entity_registry = async_get_entity_registry(hass)
    entities = {}
    
    for entity_id, entry in entity_registry.entities.items():
        if (
            entry.domain == "sensor"
            and entry.device_class == "power"
            and not entry.disabled_by
        ):
            # Get friendly name from state or use entity name
            state = hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            entities[entity_id] = friendly_name
    
    # Also check current states for entities that might not be in registry
    for state in hass.states.async_all("sensor"):
        if (
            state.entity_id not in entities
            and state.attributes.get("device_class") == "power"
        ):
            friendly_name = state.attributes.get("friendly_name", state.entity_id)
            entities[state.entity_id] = friendly_name
    
    return entities


def _get_energy_entities(hass: HomeAssistant) -> dict[str, str]:
    """Get all energy sensor entities with their friendly names."""
    entity_registry = async_get_entity_registry(hass)
    entities = {}
    
    for entity_id, entry in entity_registry.entities.items():
        if (
            entry.domain == "sensor"
            and entry.device_class == "energy"
            and not entry.disabled_by
        ):
            # Get friendly name from state or use entity name
            state = hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            entities[entity_id] = friendly_name
    
    # Also check current states for entities that might not be in registry
    for state in hass.states.async_all("sensor"):
        if (
            state.entity_id not in entities
            and state.attributes.get("device_class") == "energy"
        ):
            friendly_name = state.attributes.get("friendly_name", state.entity_id)
            entities[state.entity_id] = friendly_name
    
    return entities


class PhantomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phantom Power Monitoring."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_add_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a device with power and energy sensors."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_name = user_input.get("device_name", "").strip()
            power_entity = user_input.get("power_entity")
            energy_entity = user_input.get("energy_entity")
            
            # Validate input
            if not device_name:
                errors["device_name"] = "device_name_required"
            elif not power_entity and not energy_entity:
                errors["base"] = "no_sensors_selected"
            else:
                # Add device to list
                device = {
                    "name": device_name,
                    "power_entity": power_entity,
                    "energy_entity": energy_entity,
                }
                self._devices.append(device)
                
                # Ask if user wants to add another device
                return await self.async_step_add_another()

        power_entities_dict = _get_power_entities(self.hass)
        energy_entities_dict = _get_energy_entities(self.hass)

        # Create selector options
        power_options = [
            selector.SelectOptionDict(value=entity_id, label=friendly_name)
            for entity_id, friendly_name in sorted(power_entities_dict.items(), key=lambda x: x[1])
        ]
        
        energy_options = [
            selector.SelectOptionDict(value=entity_id, label=friendly_name)
            for entity_id, friendly_name in sorted(energy_entities_dict.items(), key=lambda x: x[1])
        ]

        data_schema = vol.Schema(
            {
                vol.Required("device_name"): str,
                vol.Optional("power_entity"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=power_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional("energy_entity"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=energy_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="add_device",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask if user wants to add another device."""
        if user_input is not None:
            if user_input.get("add_another", False):
                return await self.async_step_add_device()
            else:
                return await self.async_step_upstream()

        # Show current devices
        device_list = "\n".join([
            f"• {device['name']}"
            for device in self._devices
        ])

        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema({
                vol.Required("add_another", default=False): bool,
            }),
            description_placeholders={"devices": device_list},
        )

    async def async_step_upstream(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle upstream entity selection."""
        if user_input is not None:
            self._data.update(user_input)
            
            # Convert devices to legacy format for compatibility
            power_entities = []
            energy_entities = []
            
            for device in self._devices:
                if device.get("power_entity"):
                    power_entities.append(device["power_entity"])
                if device.get("energy_entity"):
                    energy_entities.append(device["energy_entity"])
            
            self._data[CONF_DEVICES] = self._devices
            self._data[CONF_POWER_ENTITIES] = power_entities
            self._data[CONF_ENERGY_ENTITIES] = energy_entities
            
            # Create unique ID based on devices
            if self._devices:
                unique_id = f"phantom_{self._devices[0]['name'].lower().replace(' ', '_')}"
                title = f"Phantom ({len(self._devices)} devices)"
            else:
                unique_id = "phantom_default"
                title = "Phantom"
                
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=title,
                data=self._data,
            )

        # Build schema for upstream entities
        schema_dict = {}
        
        # Check if we have power or energy entities
        has_power = any(device.get("power_entity") for device in self._devices)
        has_energy = any(device.get("energy_entity") for device in self._devices)
        
        if has_power:
            power_entities_dict = _get_power_entities(self.hass)
            used_power_entities = [device["power_entity"] for device in self._devices if device.get("power_entity")]
            
            upstream_power_options = [
                selector.SelectOptionDict(value=entity_id, label=friendly_name)
                for entity_id, friendly_name in sorted(power_entities_dict.items(), key=lambda x: x[1])
                if entity_id not in used_power_entities
            ]
            
            schema_dict[vol.Optional(CONF_UPSTREAM_POWER_ENTITY)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=upstream_power_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )
        
        if has_energy:
            energy_entities_dict = _get_energy_entities(self.hass)
            used_energy_entities = [device["energy_entity"] for device in self._devices if device.get("energy_entity")]
            
            upstream_energy_options = [
                selector.SelectOptionDict(value=entity_id, label=friendly_name)
                for entity_id, friendly_name in sorted(energy_entities_dict.items(), key=lambda x: x[1])
                if entity_id not in used_energy_entities
            ]
            
            schema_dict[vol.Optional(CONF_UPSTREAM_ENERGY_ENTITY)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=upstream_energy_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="upstream",
            data_schema=data_schema,
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
        """Manage the options - for now, redirect to reconfigure."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )