"""Sensor platform for Phantom Power Monitoring with Multi-Group Support."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_GROUPS,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    CONF_TARIFF,
    CONF_TARIFF_RATE_ENTITY,
    CONF_TARIFF_PERIOD_ENTITY,
    DOMAIN,
)
from .state_migration import clear_migration_data
from .tariff import TariffManager
from .tariff_external import ExternalTariffManager
from .utils import sanitize_name

# Import all sensor types from the sensors package
from .sensors import (
    PhantomPowerSensor,
    PhantomIndividualPowerSensor,
    PhantomEnergySensor,
    PhantomUtilityMeterSensor,
    PhantomUpstreamPowerSensor,
    PhantomUpstreamEnergyMeterSensor,
    PhantomUpstreamCostSensor,
    PhantomPowerRemainderSensor,
    PhantomEnergyRemainderSensor,
    PhantomDeviceHourlyCostSensor,
    PhantomGroupHourlyCostSensor,
    PhantomTouRateSensor,
    PhantomDeviceTotalCostSensor,
    PhantomGroupTotalCostSensor,
)
from .sensors.remainder_cost_energy_based import PhantomEnergyBasedCostRemainderSensor

_LOGGER = logging.getLogger(__name__)


def _register_entity_for_reset(hass: HomeAssistant, config_entry_id: str, entity: SensorEntity) -> None:
    """Register an entity for reset functionality."""
    if hasattr(entity, "_group_name") and hasattr(entity, "async_reset"):
        group_name = entity._group_name
        if "entities_by_group" not in hass.data[DOMAIN][config_entry_id]:
            hass.data[DOMAIN][config_entry_id]["entities_by_group"] = {}
        if group_name not in hass.data[DOMAIN][config_entry_id]["entities_by_group"]:
            hass.data[DOMAIN][config_entry_id]["entities_by_group"][group_name] = []
        hass.data[DOMAIN][config_entry_id]["entities_by_group"][group_name].append(entity)
        _LOGGER.debug("Registered %s for reset in group '%s'", type(entity).__name__, group_name)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Phantom sensors."""
    _LOGGER.info("Setting up Phantom sensors for config entry: %s", config_entry.entry_id)
    config = hass.data[DOMAIN][config_entry.entry_id]
    _LOGGER.debug("Config data: %s", config)
    
    entities = []
    
    groups = config.get(CONF_GROUPS, [])
    tariff_config = config.get(CONF_TARIFF)
    _LOGGER.info("Setting up Phantom sensors for %d groups", len(groups))
    
    for group_index, group in enumerate(groups):
        group_name = group.get(CONF_GROUP_NAME, f"Group {group_index + 1}")
        group_id = group.get(CONF_GROUP_ID)
        devices = group.get(CONF_DEVICES, [])
        upstream_power_entity = group.get(CONF_UPSTREAM_POWER_ENTITY)
        upstream_energy_entity = group.get(CONF_UPSTREAM_ENERGY_ENTITY)
        
        _LOGGER.info(
            "Setting up group '%s' (id: %s, index %d) with %d devices, upstream_power=%s, upstream_energy=%s",
            group_name,
            group_id,
            group_index,
            len(devices),
            upstream_power_entity,
            upstream_energy_entity
        )
        
        # Create sensors for this group
        try:
            group_entities = await _create_group_sensors(
                hass,
                config_entry,
                group_name,
                group_id,
                devices,
                upstream_power_entity,
                upstream_energy_entity,
                tariff_config,
                async_add_entities,
            )
            _LOGGER.info("Created %d entities for group '%s'", len(group_entities), group_name)
            entities.extend(group_entities)
        except Exception as e:
            _LOGGER.error("Error creating sensors for group '%s': %s", group_name, e, exc_info=True)
    
    # Add all entities
    if entities:
        async_add_entities(entities)
        
        # Store entities by group for reset functionality
        if "entities_by_group" not in hass.data[DOMAIN][config_entry.entry_id]:
            hass.data[DOMAIN][config_entry.entry_id]["entities_by_group"] = {}
        
        # Group entities by their group name
        for entity in entities:
            _register_entity_for_reset(hass, config_entry.entry_id, entity)
        
        # Schedule clearing migration data after entities have been initialized
        async def clear_migration_after_delay():
            """Clear migration data after entities have had time to restore states."""
            await asyncio.sleep(2.0)  # Give entities time to initialize and restore states
            clear_migration_data(hass, config_entry.entry_id)
            _LOGGER.debug("Cleared migration data after entity initialization")
        
        hass.async_create_task(clear_migration_after_delay())
    else:
        _LOGGER.warning("No entities created for Phantom integration")


async def _create_group_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    group_name: str,
    group_id: str | None,
    devices: list[dict[str, Any]],
    upstream_power_entity: str | None,
    upstream_energy_entity: str | None,
    tariff_config: dict[str, Any] | None,
    async_add_entities: AddEntitiesCallback,
) -> list[SensorEntity]:
    """Create sensors for a single group."""
    _LOGGER.debug("Creating sensors for group '%s' (id: %s)", group_name, group_id)
    entities = []
    
    # Create tariff manager for this group
    if tariff_config and (tariff_config.get(CONF_TARIFF_RATE_ENTITY) or tariff_config.get(CONF_TARIFF_PERIOD_ENTITY)):
        # Use external tariff manager if external sensors are configured
        tariff_manager = ExternalTariffManager(
            hass,
            tariff_config,
            tariff_config.get(CONF_TARIFF_RATE_ENTITY),
            tariff_config.get(CONF_TARIFF_PERIOD_ENTITY),
        )
        # Setup listeners for external sensors
        tariff_manager.setup()
        
        # Store the tariff manager for cleanup
        if "tariff_managers" not in hass.data[DOMAIN][config_entry.entry_id]:
            hass.data[DOMAIN][config_entry.entry_id]["tariff_managers"] = []
        hass.data[DOMAIN][config_entry.entry_id]["tariff_managers"].append(tariff_manager)
    else:
        # Use internal tariff manager
        tariff_manager = TariffManager(tariff_config)
    
    # Collect power and energy entities from devices
    power_entities = []
    energy_entities = []
    individual_power_entities = []
    
    _LOGGER.debug("Processing %d devices for group '%s'", len(devices), group_name)
    
    for device in devices:
        device_name = device.get("name", "Unknown")
        device_id = device.get(CONF_DEVICE_ID)
        power_entity = device.get("power_entity")
        energy_entity = device.get("energy_entity")
        
        _LOGGER.debug(
            "Device '%s' (id: %s): power_entity=%s, energy_entity=%s",
            device_name,
            device_id,
            power_entity,
            energy_entity
        )
        
        if power_entity:
            power_entities.append(power_entity)
            # Create individual power sensor
            individual_sensor = PhantomIndividualPowerSensor(
                config_entry.entry_id,
                group_name,
                device_name,
                device_id,
                power_entity,
            )
            entities.append(individual_sensor)
            individual_power_entities.append(individual_sensor)
            _LOGGER.debug("Created individual power sensor for device '%s'", device_name)
            
            # Create hourly cost sensor if tariff is enabled
            if tariff_manager.enabled:
                entities.append(
                    PhantomDeviceHourlyCostSensor(
                        hass,
                        config_entry.entry_id,
                        group_name,
                        device_name,
                        device_id,
                        power_entity,
                        tariff_manager,
                    )
                )
                _LOGGER.debug("Created hourly cost sensor for device '%s'", device_name)
        
        if energy_entity:
            energy_entities.append(energy_entity)
            # Create individual utility meter sensor
            entities.append(
                PhantomUtilityMeterSensor(
                    hass,
                    config_entry.entry_id,
                    group_name,
                    device_name,
                    device_id,
                    energy_entity,
                )
            )
            _LOGGER.debug("Created utility meter sensor for device '%s'", device_name)
            
            # Create total cost sensor if tariff is enabled
            if tariff_manager.enabled:
                # Total cost sensor will be created after a delay to track the utility meter
                _LOGGER.debug("Total cost sensor for device '%s' will be created after utility meter is ready", device_name)
    
    # Create group power total sensor
    if power_entities:
        entities.append(
            PhantomPowerSensor(
                config_entry.entry_id,
                group_name,
                group_id,
                power_entities,
            )
        )
        _LOGGER.debug("Created power total sensor for group '%s'", group_name)
    else:
        _LOGGER.debug("No power entities for group '%s', skipping power total sensor", group_name)
    
    # Create group energy total sensor
    if energy_entities:
        entities.append(
            PhantomEnergySensor(
                hass,
                config_entry.entry_id,
                group_name,
                group_id,
                devices,
            )
        )
        _LOGGER.debug("Created energy total sensor for group '%s'", group_name)
    else:
        _LOGGER.debug("No energy entities for group '%s', skipping energy total sensor", group_name)
    
    # Create group cost sensors if tariff is enabled
    if tariff_manager.enabled and power_entities:
        entities.append(
            PhantomGroupHourlyCostSensor(
                hass,
                config_entry.entry_id,
                group_name,
                group_id,
                power_entities,
                tariff_manager,
            )
        )
        _LOGGER.debug("Created hourly cost sensor for group '%s'", group_name)
        
        # Create TOU rate sensor only for internal tariff configuration
        # External tariff managers get their rate from external sensors
        if not isinstance(tariff_manager, ExternalTariffManager):
            entities.append(
                PhantomTouRateSensor(
                    config_entry.entry_id,
                    group_name,
                    group_id,
                    tariff_manager,
                )
            )
            _LOGGER.debug("Created TOU rate sensor for group '%s'", group_name)
        
        # Create group total cost sensor
        entities.append(
            PhantomGroupTotalCostSensor(
                hass,
                config_entry.entry_id,
                group_name,
                group_id,
                devices,
                tariff_manager,
            )
        )
        _LOGGER.debug("Created group total cost sensor for group '%s'", group_name)
    
    # Create upstream sensors if configured
    if upstream_power_entity:
        entities.append(
            PhantomUpstreamPowerSensor(
                config_entry.entry_id,
                group_name,
                group_id,
                upstream_power_entity,
            )
        )
        _LOGGER.debug("Created upstream power sensor for group '%s'", group_name)
        
        # Create power remainder if we have both upstream and group power
        if power_entities:
            entities.append(
                PhantomPowerRemainderSensor(
                    config_entry.entry_id,
                    group_name,
                    group_id,
                    upstream_power_entity,
                    power_entities,
                )
            )
            _LOGGER.debug("Created power remainder sensor for group '%s'", group_name)
    
    if upstream_energy_entity:
        entities.append(
            PhantomUpstreamEnergyMeterSensor(
                hass,
                config_entry.entry_id,
                group_name,
                group_id,
                upstream_energy_entity,
            )
        )
        _LOGGER.debug("Created upstream energy meter sensor for group '%s'", group_name)
        
        # Create energy remainder if we have both upstream and group energy
        if energy_entities:
            entities.append(
                PhantomEnergyRemainderSensor(
                    hass,
                    config_entry.entry_id,
                    group_name,
                    group_id,
                    upstream_energy_entity,
                    devices,
                )
            )
            _LOGGER.debug("Created energy remainder sensor for group '%s'", group_name)
    
    # Store utility meter mapping for cost sensors
    utility_meter_mapping = {}
    for device in devices:
        device_id = device.get(CONF_DEVICE_ID)
        if device_id:
            utility_meter_mapping[device_id] = f"{device_id}_utility_meter"
    
    # Store sensor mappings for delayed sensors
    if "sensor_mappings" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["sensor_mappings"] = {}
    
    mappings = hass.data[DOMAIN][config_entry.entry_id]["sensor_mappings"]
    mappings[group_name] = {
        "upstream_meter": f"{group_id}_upstream_energy_meter" if group_id else f"{config_entry.entry_id}_{sanitize_name(group_name)}_upstream_energy_meter",
        "energy_remainder": f"{group_id}_energy_remainder" if group_id else f"{config_entry.entry_id}_{sanitize_name(group_name)}_energy_remainder",
        "utility_meters": utility_meter_mapping,
    }
    
    # Create delayed total cost sensors if tariff is enabled
    if tariff_manager.enabled:
        # Schedule creation of total cost sensors after utility meters are ready
        async def create_total_cost_sensors():
            """Create total cost sensors with retry logic."""
            _LOGGER.info("Starting delayed creation of total cost sensors for group '%s'", group_name)
            
            # Get stored mappings
            mappings = hass.data[DOMAIN][config_entry.entry_id]["sensor_mappings"][group_name]
            
            # Single short delay to allow entities to be registered
            await asyncio.sleep(1.0)
            
            _LOGGER.info("Creating total cost sensors for group '%s' after 1s delay", group_name)
            
            entity_registry = er.async_get(hass)
            cost_entities = []
            devices_to_process = []
            
            for device in devices:
                device_name = device.get("name", "Unknown")
                device_id = device.get(CONF_DEVICE_ID)
                
                if device_id and device.get("energy_entity"):
                    devices_to_process.append((device_name, device_id))
                    
                    # Get the utility meter entity from mappings
                    expected_unique_id = mappings["utility_meters"].get(device_id)
                    utility_meter_entity = None
                    
                    if expected_unique_id:
                        _LOGGER.debug("Looking for utility meter with unique_id: %s", expected_unique_id)
                        
                        for entity_id, entry in entity_registry.entities.items():
                            if (
                                entry.unique_id == expected_unique_id
                                and entry.domain == "sensor"
                                and entry.platform == DOMAIN
                            ):
                                utility_meter_entity = entity_id
                                break
                    
                    if utility_meter_entity:
                        # Verify entity has a valid state
                        state = hass.states.get(utility_meter_entity)
                        if state is None:
                            _LOGGER.warning(
                                "Utility meter %s found in registry but not in state machine",
                                utility_meter_entity
                            )
                            continue
                        
                        # Create total cost sensor
                        cost_sensor = PhantomDeviceTotalCostSensor(
                            hass,
                            config_entry.entry_id,
                            group_name,
                            device_name,
                            device_id,
                            utility_meter_entity,
                            tariff_manager,
                        )
                        cost_entities.append(cost_sensor)
                        _LOGGER.info(
                            "Created delayed total cost sensor for device '%s' tracking %s (state: %s)",
                            device_name,
                            utility_meter_entity,
                            state.state
                        )
                    else:
                        _LOGGER.debug(
                            "Could not find utility meter entity for device '%s' with ID %s",
                            device_name,
                            device_id
                        )
                
            
            # Add the cost sensors
            if cost_entities:
                async_add_entities(cost_entities)
                # Register each cost entity for reset
                for cost_entity in cost_entities:
                    _register_entity_for_reset(hass, config_entry.entry_id, cost_entity)
                _LOGGER.info("Added %d delayed total cost sensors for group '%s'", len(cost_entities), group_name)
                
                # Create cost remainder sensor if we have an energy remainder sensor
                # Find energy remainder entity
                energy_remainder_entity = None
                if upstream_energy_entity and energy_entities:
                    # Get from stored mappings
                    expected_energy_remainder_id = mappings["energy_remainder"]
                    
                    for entity_id, entry in entity_registry.entities.items():
                        if (entry.unique_id == expected_energy_remainder_id and 
                            entry.domain == "sensor" and
                            entry.platform == DOMAIN):
                            energy_remainder_entity = entity_id
                            _LOGGER.debug("Found energy remainder entity: %s", energy_remainder_entity)
                            break
                
                if energy_remainder_entity:
                    cost_remainder_sensor = PhantomEnergyBasedCostRemainderSensor(
                        hass,
                        config_entry.entry_id,
                        group_name,
                        group_id,
                        energy_remainder_entity,
                        tariff_manager,
                    )
                    async_add_entities([cost_remainder_sensor])
                    _register_entity_for_reset(hass, config_entry.entry_id, cost_remainder_sensor)
                    _LOGGER.info(
                        "Created cost remainder sensor for group '%s' tracking energy remainder %s",
                        group_name,
                        energy_remainder_entity
                    )
                
                # Create upstream cost sensor if we have an upstream energy meter
                if upstream_energy_entity:
                    # Get from stored mappings
                    upstream_meter_entity = None
                    expected_upstream_meter_id = mappings["upstream_meter"]
                    
                    for entity_id, entry in entity_registry.entities.items():
                        if (entry.unique_id == expected_upstream_meter_id and 
                            entry.domain == "sensor" and
                            entry.platform == DOMAIN):
                            upstream_meter_entity = entity_id
                            _LOGGER.debug("Found upstream meter entity: %s", upstream_meter_entity)
                            break
                    
                    if upstream_meter_entity:
                        upstream_cost_sensor = PhantomUpstreamCostSensor(
                            hass,
                            config_entry.entry_id,
                            group_name,
                            group_id,
                            upstream_meter_entity,
                            tariff_manager,
                        )
                        async_add_entities([upstream_cost_sensor])
                        _register_entity_for_reset(hass, config_entry.entry_id, upstream_cost_sensor)
                        _LOGGER.info(
                            "Created upstream cost sensor for group '%s' tracking upstream meter %s",
                            group_name,
                            upstream_meter_entity
                        )
            else:
                _LOGGER.warning(
                    "No total cost sensors created for group '%s' - no utility meters found",
                    group_name
                )
        
        # Store the task reference for the create function
        if "total_cost_tasks" not in hass.data[DOMAIN][config_entry.entry_id]:
            hass.data[DOMAIN][config_entry.entry_id]["total_cost_tasks"] = []
        
        task = hass.async_create_task(create_total_cost_sensors())
        hass.data[DOMAIN][config_entry.entry_id]["total_cost_tasks"].append(task)
    
    _LOGGER.info("Created total of %d entities for group '%s'", len(entities), group_name)
    return entities