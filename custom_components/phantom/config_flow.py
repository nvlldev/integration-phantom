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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Process the submitted form
            devices = []
            device_count = 0
            
            # Count how many devices were configured
            while f"device_{device_count}_name" in user_input:
                device_name = user_input.get(f"device_{device_count}_name", "").strip()
                power_entity = user_input.get(f"device_{device_count}_power")
                energy_entity = user_input.get(f"device_{device_count}_energy")
                
                # Only add device if it has a name and at least one sensor
                if device_name and (power_entity or energy_entity):
                    devices.append({
                        "name": device_name,
                        "power_entity": power_entity,
                        "energy_entity": energy_entity,
                    })
                
                device_count += 1
            
            if not devices:
                errors["base"] = "no_devices_configured"
            else:
                # Convert devices to legacy format for compatibility
                power_entities = []
                energy_entities = []
                
                for device in devices:
                    if device.get("power_entity"):
                        power_entities.append(device["power_entity"])
                    if device.get("energy_entity"):
                        energy_entities.append(device["energy_entity"])
                
                self._data[CONF_DEVICES] = devices
                self._data[CONF_POWER_ENTITIES] = power_entities
                self._data[CONF_ENERGY_ENTITIES] = energy_entities
                self._data[CONF_UPSTREAM_POWER_ENTITY] = user_input.get(CONF_UPSTREAM_POWER_ENTITY)
                self._data[CONF_UPSTREAM_ENERGY_ENTITY] = user_input.get(CONF_UPSTREAM_ENERGY_ENTITY)
                
                # Create unique ID based on devices
                if devices:
                    unique_id = f"phantom_{devices[0]['name'].lower().replace(' ', '_')}"
                    title = f"Phantom ({len(devices)} devices)"
                else:
                    unique_id = "phantom_default"
                    title = "Phantom"
                    
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=title,
                    data=self._data,
                )

        # Build the form schema
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

        # Start with one device by default
        num_devices = 1
        if user_input:
            # Count existing devices from previous form submission
            device_count = 0
            while f"device_{device_count}_name" in user_input:
                device_count += 1
            num_devices = max(1, device_count)
            
            # Check if user clicked add device
            if user_input.get("add_device"):
                num_devices += 1

        schema_dict = {}
        
        # Add device configuration fields
        for i in range(num_devices):
            schema_dict[vol.Optional(f"device_{i}_name", default="")] = str
            schema_dict[vol.Optional(f"device_{i}_power")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=power_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )
            schema_dict[vol.Optional(f"device_{i}_energy")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=energy_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )
        
        # Add "Add Device" button
        schema_dict[vol.Optional("add_device", default=False)] = bool
        
        # Add upstream entity selectors
        if power_options:
            schema_dict[vol.Optional(CONF_UPSTREAM_POWER_ENTITY)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=power_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )
        
        if energy_options:
            schema_dict[vol.Optional(CONF_UPSTREAM_ENERGY_ENTITY)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=energy_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
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