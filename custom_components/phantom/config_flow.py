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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_entities_by_device_class(hass: HomeAssistant, device_class: str) -> dict[str, str]:
    """Get all sensor entities with specified device class and their friendly names."""
    entity_registry = async_get_entity_registry(hass)
    entities = {}
    
    # Get from entity registry
    for entity_id, entry in entity_registry.entities.items():
        if (
            entry.domain == "sensor"
            and entry.device_class == device_class
            and not entry.disabled_by
        ):
            state = hass.states.get(entity_id)
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id
            entities[entity_id] = friendly_name
    
    # Also check current states for entities not in registry
    for state in hass.states.async_all("sensor"):
        if (
            state.entity_id not in entities
            and state.attributes.get("device_class") == device_class
        ):
            friendly_name = state.attributes.get("friendly_name", state.entity_id)
            entities[state.entity_id] = friendly_name
    
    return entities


def _create_entity_selector(entities_dict: dict[str, str]) -> selector.SelectSelector:
    """Create a SelectSelector from entities dictionary."""
    options = [
        selector.SelectOptionDict(value=entity_id, label=friendly_name)
        for entity_id, friendly_name in sorted(entities_dict.items(), key=lambda x: x[1])
    ]
    
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.DROPDOWN,
        ),
    )


class PhantomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phantom Power Monitoring."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_name = user_input.get("device_name", "").strip()
            power_entity = user_input.get("power_entity")
            energy_entity = user_input.get("energy_entity")
            
            if not device_name:
                errors["device_name"] = "device_name_required"
            elif not power_entity and not energy_entity:
                errors["base"] = "no_sensors_selected"
            else:
                # Add device to list
                self._devices.append({
                    "name": device_name,
                    "power_entity": power_entity,
                    "energy_entity": energy_entity,
                })
                
                # Check if user wants to add another device
                if user_input.get("add_another", False):
                    return await self.async_step_device()
                else:
                    return await self.async_step_upstream()

        # Get available entities
        power_entities = _get_entities_by_device_class(self.hass, "power")
        energy_entities = _get_entities_by_device_class(self.hass, "energy")

        data_schema = vol.Schema({
            vol.Required("device_name"): str,
            vol.Optional("power_entity"): _create_entity_selector(power_entities),
            vol.Optional("energy_entity"): _create_entity_selector(energy_entities),
            vol.Optional("add_another", default=False): bool,
        })

        return self.async_show_form(
            step_id="device",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._devices)),
                "devices": ", ".join([device["name"] for device in self._devices]) if self._devices else "None"
            },
        )

    async def async_step_upstream(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle upstream entity selection."""
        if user_input is not None:
            data = {
                CONF_DEVICES: self._devices,
                CONF_UPSTREAM_POWER_ENTITY: user_input.get(CONF_UPSTREAM_POWER_ENTITY),
                CONF_UPSTREAM_ENERGY_ENTITY: user_input.get(CONF_UPSTREAM_ENERGY_ENTITY),
            }
            
            # Create unique ID and title
            if self._devices:
                unique_id = f"phantom_{self._devices[0]['name'].lower().replace(' ', '_')}"
                title = f"Phantom ({len(self._devices)} devices)"
            else:
                unique_id = "phantom_default"
                title = "Phantom"
                
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=title, data=data)

        # If no devices were added, force them to add at least one
        if not self._devices:
            return await self.async_step_device()

        # Build upstream entity options (exclude already used entities)
        schema_dict = {}
        used_power_entities = {device["power_entity"] for device in self._devices if device.get("power_entity")}
        used_energy_entities = {device["energy_entity"] for device in self._devices if device.get("energy_entity")}
        
        # Power upstream selector
        if any(device.get("power_entity") for device in self._devices):
            power_entities = _get_entities_by_device_class(self.hass, "power")
            available_power = {k: v for k, v in power_entities.items() if k not in used_power_entities}
            
            if available_power:
                schema_dict[vol.Optional(CONF_UPSTREAM_POWER_ENTITY)] = _create_entity_selector(available_power)
        
        # Energy upstream selector
        if any(device.get("energy_entity") for device in self._devices):
            energy_entities = _get_entities_by_device_class(self.hass, "energy")
            available_energy = {k: v for k, v in energy_entities.items() if k not in used_energy_entities}
            
            if available_energy:
                schema_dict[vol.Optional(CONF_UPSTREAM_ENERGY_ENTITY)] = _create_entity_selector(available_energy)

        device_list = "\n".join([
            f"• {device['name']} (Power: {device.get('power_entity', 'None')}, Energy: {device.get('energy_entity', 'None')})"
            for device in self._devices
        ])

        return self.async_show_form(
            step_id="upstream",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"devices": device_list},
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
        self._devices = list(config_entry.data.get(CONF_DEVICES, []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_device":
                return await self.async_step_add_device()
            elif action == "manage_devices":
                return await self.async_step_manage_devices()
            elif action == "upstream":
                return await self.async_step_upstream()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="add_device", label="Add Device"),
                            selector.SelectOptionDict(value="manage_devices", label="Manage Devices"),
                            selector.SelectOptionDict(value="upstream", label="Configure Upstream"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            }),
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_name = user_input.get("device_name", "").strip()
            power_entity = user_input.get("power_entity")
            energy_entity = user_input.get("energy_entity")
            
            if not device_name:
                errors["device_name"] = "device_name_required"
            elif not power_entity and not energy_entity:
                errors["base"] = "no_sensors_selected"
            else:
                # Add device to list and save
                self._devices.append({
                    "name": device_name,
                    "power_entity": power_entity,
                    "energy_entity": energy_entity,
                })
                return await self._save_config()

        # Get available entities
        power_entities = _get_entities_by_device_class(self.hass, "power")
        energy_entities = _get_entities_by_device_class(self.hass, "energy")

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema({
                vol.Required("device_name"): str,
                vol.Optional("power_entity"): _create_entity_selector(power_entities),
                vol.Optional("energy_entity"): _create_entity_selector(energy_entities),
            }),
            errors=errors,
        )

    async def async_step_manage_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage existing devices."""
        if user_input is not None:
            selected_devices = user_input.get("devices", [])
            # Keep only selected devices
            self._devices = [
                device for i, device in enumerate(self._devices) 
                if str(i) in selected_devices
            ]
            return await self._save_config()

        if not self._devices:
            return await self.async_step_init()

        device_options = [
            selector.SelectOptionDict(
                value=str(i),
                label=f"{device['name']} (Power: {device.get('power_entity', 'None')}, Energy: {device.get('energy_entity', 'None')})"
            )
            for i, device in enumerate(self._devices)
        ]

        return self.async_show_form(
            step_id="manage_devices",
            data_schema=vol.Schema({
                vol.Optional("devices", default=[str(i) for i in range(len(self._devices))]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=device_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
            }),
        )

    async def async_step_upstream(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure upstream entities."""
        if user_input is not None:
            # Update config with new upstream settings
            updated_data = dict(self.config_entry.data)
            updated_data[CONF_UPSTREAM_POWER_ENTITY] = user_input.get(CONF_UPSTREAM_POWER_ENTITY)
            updated_data[CONF_UPSTREAM_ENERGY_ENTITY] = user_input.get(CONF_UPSTREAM_ENERGY_ENTITY)
            updated_data[CONF_DEVICES] = self._devices
            
            return self.async_create_entry(title="", data=updated_data)

        # Get current upstream values
        current_upstream_power = self.config_entry.data.get(CONF_UPSTREAM_POWER_ENTITY)
        current_upstream_energy = self.config_entry.data.get(CONF_UPSTREAM_ENERGY_ENTITY)

        # Build upstream options (exclude used entities)
        schema_dict = {}
        used_power_entities = {device["power_entity"] for device in self._devices if device.get("power_entity")}
        used_energy_entities = {device["energy_entity"] for device in self._devices if device.get("energy_entity")}
        
        # Power upstream
        if any(device.get("power_entity") for device in self._devices):
            power_entities = _get_entities_by_device_class(self.hass, "power")
            available_power = {k: v for k, v in power_entities.items() if k not in used_power_entities}
            
            if available_power:
                schema_dict[vol.Optional(CONF_UPSTREAM_POWER_ENTITY, default=current_upstream_power)] = _create_entity_selector(available_power)

        # Energy upstream
        if any(device.get("energy_entity") for device in self._devices):
            energy_entities = _get_entities_by_device_class(self.hass, "energy")
            available_energy = {k: v for k, v in energy_entities.items() if k not in used_energy_entities}
            
            if available_energy:
                schema_dict[vol.Optional(CONF_UPSTREAM_ENERGY_ENTITY, default=current_upstream_energy)] = _create_entity_selector(available_energy)

        return self.async_show_form(
            step_id="upstream",
            data_schema=vol.Schema(schema_dict),
        )

    async def _save_config(self) -> FlowResult:
        """Save the updated configuration."""
        updated_data = dict(self.config_entry.data)
        updated_data[CONF_DEVICES] = self._devices
        
        return self.async_create_entry(title="", data=updated_data)