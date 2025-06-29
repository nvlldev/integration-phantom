"""Config flow for Phantom Power Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import sensor
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    CONF_ENERGY_ENTITIES,
    CONF_POWER_ENTITIES,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_power_entities(hass: HomeAssistant) -> list[str]:
    """Get all power sensor entities."""
    entity_registry = async_get_entity_registry(hass)
    entities = []
    
    for entity_id, entry in entity_registry.entities.items():
        if (
            entry.domain == "sensor"
            and entry.device_class == "power"
            and not entry.disabled_by
        ):
            entities.append(entity_id)
    
    # Also check current states for entities that might not be in registry
    for state in hass.states.async_all("sensor"):
        if (
            state.entity_id not in entities
            and state.attributes.get("device_class") == "power"
        ):
            entities.append(state.entity_id)
    
    return sorted(entities)


def _get_energy_entities(hass: HomeAssistant) -> list[str]:
    """Get all energy sensor entities."""
    entity_registry = async_get_entity_registry(hass)
    entities = []
    
    for entity_id, entry in entity_registry.entities.items():
        if (
            entry.domain == "sensor"
            and entry.device_class == "energy"
            and not entry.disabled_by
        ):
            entities.append(entity_id)
    
    # Also check current states for entities that might not be in registry
    for state in hass.states.async_all("sensor"):
        if (
            state.entity_id not in entities
            and state.attributes.get("device_class") == "energy"
        ):
            entities.append(state.entity_id)
    
    return sorted(entities)


class PhantomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phantom Power Monitoring."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that at least one entity type is selected
            power_entities = user_input.get(CONF_POWER_ENTITIES, [])
            energy_entities = user_input.get(CONF_ENERGY_ENTITIES, [])
            
            if not power_entities and not energy_entities:
                errors["base"] = "no_entities_selected"
            else:
                self._data.update(user_input)
                return await self.async_step_upstream()

        power_entities = _get_power_entities(self.hass)
        energy_entities = _get_energy_entities(self.hass)

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_POWER_ENTITIES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=power_entities,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(CONF_ENERGY_ENTITIES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=energy_entities,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),    
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_upstream(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle upstream entity selection."""
        if user_input is not None:
            self._data.update(user_input)
            
            # Create unique ID based on selected entities
            power_entities = self._data.get(CONF_POWER_ENTITIES, [])
            energy_entities = self._data.get(CONF_ENERGY_ENTITIES, [])
            
            # Use first entity or create generic ID
            if power_entities:
                unique_id = f"phantom_{power_entities[0]}"
                title = f"Phantom ({len(power_entities)} power entities)"
            elif energy_entities:
                unique_id = f"phantom_{energy_entities[0]}"
                title = f"Phantom ({len(energy_entities)} energy entities)"
            else:
                unique_id = "phantom_default"
                title = "Phantom"
                
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=title,
                data=self._data,
            )

        # Build schema based on what entity types are configured
        schema_dict = {}
        
        # Add upstream power entity selection if power entities are configured
        power_entities_configured = self._data.get(CONF_POWER_ENTITIES, [])
        if power_entities_configured:
            all_power_entities = _get_power_entities(self.hass)
            upstream_power_options = [
                entity for entity in all_power_entities 
                if entity not in power_entities_configured
            ]
            schema_dict[vol.Optional(CONF_UPSTREAM_POWER_ENTITY)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=upstream_power_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            )
        
        # Add upstream energy entity selection if energy entities are configured
        energy_entities_configured = self._data.get(CONF_ENERGY_ENTITIES, [])
        if energy_entities_configured:
            all_energy_entities = _get_energy_entities(self.hass)
            upstream_energy_options = [
                entity for entity in all_energy_entities 
                if entity not in energy_entities_configured
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
            description_placeholders={"group_name": self._data[CONF_GROUP_NAME]},
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
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Validate that at least one entity type is selected
            power_entities = user_input.get(CONF_POWER_ENTITIES, [])
            energy_entities = user_input.get(CONF_ENERGY_ENTITIES, [])
            
            if not power_entities and not energy_entities:
                errors["base"] = "no_entities_selected"
            else:
                return self.async_create_entry(title="", data=user_input)

        power_entities = _get_power_entities(self.hass)
        energy_entities = _get_energy_entities(self.hass)

        # Get current values from both data and options (options take precedence)
        config = {**self.config_entry.data}
        if self.config_entry.options:
            config.update(self.config_entry.options)
            
        current_power_entities = config.get(CONF_POWER_ENTITIES, [])
        current_energy_entities = config.get(CONF_ENERGY_ENTITIES, [])
        current_upstream_power = config.get(CONF_UPSTREAM_POWER_ENTITY)
        current_upstream_energy = config.get(CONF_UPSTREAM_ENERGY_ENTITY)

        # Remove currently selected entities from upstream options
        upstream_power_options = [
            entity for entity in power_entities 
            if entity not in current_power_entities
        ]
        
        upstream_energy_options = [
            entity for entity in energy_entities 
            if entity not in current_energy_entities
        ]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POWER_ENTITIES, 
                    default=current_power_entities
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=power_entities,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(
                    CONF_ENERGY_ENTITIES, 
                    default=current_energy_entities
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=energy_entities,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(
                    CONF_UPSTREAM_POWER_ENTITY,
                    default=current_upstream_power
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=upstream_power_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(
                    CONF_UPSTREAM_ENERGY_ENTITY,
                    default=current_upstream_energy
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=upstream_energy_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )