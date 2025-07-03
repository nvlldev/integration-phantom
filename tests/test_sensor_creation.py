"""Test sensor creation to ensure all sensors are properly created."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from custom_components.phantom.const import (
    DOMAIN,
    CONF_GROUPS,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    CONF_TARIFF,
    CONF_TARIFF_ENABLED,
    CONF_TARIFF_RATE_TYPE,
    CONF_TARIFF_FLAT_RATE,
    TARIFF_TYPE_FLAT,
)


@pytest.fixture
def complete_config():
    """Return a complete configuration with all features enabled."""
    return {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Living Room",
                CONF_GROUP_ID: str(uuid.uuid4()),
                CONF_UPSTREAM_POWER_ENTITY: "sensor.main_power",
                CONF_UPSTREAM_ENERGY_ENTITY: "sensor.main_energy",
                CONF_DEVICES: [
                    {
                        "name": "TV",
                        CONF_DEVICE_ID: str(uuid.uuid4()),
                        "power_entity": "sensor.tv_power",
                        "energy_entity": "sensor.tv_energy",
                    },
                    {
                        "name": "Sound System",
                        CONF_DEVICE_ID: str(uuid.uuid4()),
                        "power_entity": "sensor.sound_power",
                        "energy_entity": "sensor.sound_energy",
                    },
                ],
            },
            {
                CONF_GROUP_NAME: "Kitchen",
                CONF_GROUP_ID: str(uuid.uuid4()),
                CONF_DEVICES: [
                    {
                        "name": "Refrigerator",
                        CONF_DEVICE_ID: str(uuid.uuid4()),
                        "power_entity": "sensor.fridge_power",
                        "energy_entity": "sensor.fridge_energy",
                    },
                ],
            },
        ],
        CONF_TARIFF: {
            CONF_TARIFF_ENABLED: True,
            "currency": "USD",
            "currency_symbol": "$",
            "rate_structure": {
                "type": TARIFF_TYPE_FLAT,
                CONF_TARIFF_FLAT_RATE: 0.15,
            },
        },
    }


@pytest.mark.asyncio
async def test_all_sensors_created(mock_hass, complete_config):
    """Test that all expected sensors are created for a complete configuration."""
    # Setup
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    
    # Store config in hass data
    mock_hass.data[DOMAIN] = {
        config_entry.entry_id: complete_config
    }
    
    # Track entities added
    added_entities = []
    
    def track_entities(entities):
        added_entities.extend(entities)
    
    async_add_entities = MagicMock(side_effect=track_entities)
    
    # Import and call setup
    from custom_components.phantom.sensor import async_setup_entry
    
    # Run setup
    await async_setup_entry(mock_hass, config_entry, async_add_entities)
    
    # Give delayed tasks time to run (for total cost sensors)
    await asyncio.sleep(4)
    
    # Verify entities were created
    assert len(added_entities) > 0, "No entities were created"
    
    # Count entity types
    entity_types = {}
    for entity in added_entities:
        entity_type = type(entity).__name__
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    
    print("\nCreated entities by type:")
    for entity_type, count in sorted(entity_types.items()):
        print(f"  {entity_type}: {count}")
    
    # Expected sensors for Living Room group (with upstream and 2 devices):
    # - 2 individual power sensors (TV, Sound System)
    # - 2 individual cost sensors (TV, Sound System)
    # - 2 utility meter sensors (TV, Sound System)
    # - 1 group power total
    # - 1 group energy total
    # - 1 group cost per hour
    # - 1 group total cost
    # - 1 TOU rate sensor
    # - 1 upstream power
    # - 1 upstream energy meter
    # - 1 power remainder
    # - 1 energy remainder
    # = 13 immediate + 2 delayed total cost sensors = 15 total
    
    # Expected sensors for Kitchen group (no upstream, 1 device):
    # - 1 individual power sensor (Refrigerator)
    # - 1 individual cost sensor (Refrigerator)
    # - 1 utility meter sensor (Refrigerator)
    # - 1 group power total
    # - 1 group energy total
    # - 1 group cost per hour
    # - 1 group total cost
    # - 1 TOU rate sensor
    # = 8 immediate + 1 delayed total cost sensor = 9 total
    
    # Total expected: 24 sensors
    
    # Verify specific sensor types
    assert entity_types.get("PhantomIndividualPowerSensor", 0) == 3, "Should have 3 individual power sensors"
    assert entity_types.get("PhantomUtilityMeterSensor", 0) == 3, "Should have 3 utility meter sensors"
    assert entity_types.get("PhantomPowerSensor", 0) == 2, "Should have 2 group power total sensors"
    assert entity_types.get("PhantomEnergySensor", 0) == 2, "Should have 2 group energy total sensors"
    assert entity_types.get("PhantomDeviceHourlyCostSensor", 0) == 3, "Should have 3 device hourly cost sensors"
    assert entity_types.get("PhantomGroupHourlyCostSensor", 0) == 2, "Should have 2 group hourly cost sensors"
    assert entity_types.get("PhantomTouRateSensor", 0) == 2, "Should have 2 TOU rate sensors"
    assert entity_types.get("PhantomGroupTotalCostSensor", 0) == 2, "Should have 2 group total cost sensors"
    assert entity_types.get("PhantomUpstreamPowerSensor", 0) == 1, "Should have 1 upstream power sensor"
    assert entity_types.get("PhantomUpstreamEnergyMeterSensor", 0) == 1, "Should have 1 upstream energy meter"
    assert entity_types.get("PhantomPowerRemainderSensor", 0) == 1, "Should have 1 power remainder sensor"
    assert entity_types.get("PhantomEnergyRemainderSensor", 0) == 1, "Should have 1 energy remainder sensor"
    
    # Note: PhantomDeviceTotalCostSensor entities are created with a delay
    # They would appear in a real integration after the delay
    
    print(f"\nTotal entities created: {len(added_entities)}")
    
    # Verify group tracking for reset functionality
    assert "entities_by_group" in mock_hass.data[DOMAIN][config_entry.entry_id]
    groups_with_entities = mock_hass.data[DOMAIN][config_entry.entry_id]["entities_by_group"]
    assert "Living Room" in groups_with_entities
    assert "Kitchen" in groups_with_entities
    
    # List all entity names for debugging
    print("\nAll created entities:")
    for entity in added_entities:
        print(f"  {entity._attr_name} ({type(entity).__name__})")


@pytest.mark.asyncio
async def test_minimal_sensor_creation(mock_hass):
    """Test sensor creation with minimal configuration."""
    # Minimal config - one group, one device, no tariff, no upstream
    config = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Test Group",
                CONF_GROUP_ID: str(uuid.uuid4()),
                CONF_DEVICES: [
                    {
                        "name": "Test Device",
                        CONF_DEVICE_ID: str(uuid.uuid4()),
                        "power_entity": "sensor.test_power",
                    },
                ],
            },
        ],
    }
    
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    mock_hass.data[DOMAIN] = {config_entry.entry_id: config}
    
    added_entities = []
    
    def track_entities(entities):
        added_entities.extend(entities)
    
    async_add_entities = MagicMock(side_effect=track_entities)
    
    from custom_components.phantom.sensor import async_setup_entry
    await async_setup_entry(mock_hass, config_entry, async_add_entities)
    
    # Expected: 1 individual power + 1 group power total = 2 sensors
    assert len(added_entities) == 2
    
    entity_types = [type(entity).__name__ for entity in added_entities]
    assert "PhantomIndividualPowerSensor" in entity_types
    assert "PhantomPowerSensor" in entity_types


@pytest.mark.asyncio
async def test_no_devices_sensor_creation(mock_hass):
    """Test sensor creation with no devices."""
    config = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Empty Group",
                CONF_GROUP_ID: str(uuid.uuid4()),
                CONF_DEVICES: [],
            },
        ],
    }
    
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    mock_hass.data[DOMAIN] = {config_entry.entry_id: config}
    
    added_entities = []
    
    def track_entities(entities):
        added_entities.extend(entities)
    
    async_add_entities = MagicMock(side_effect=track_entities)
    
    from custom_components.phantom.sensor import async_setup_entry
    await async_setup_entry(mock_hass, config_entry, async_add_entities)
    
    # Should create no sensors for empty group
    assert len(added_entities) == 0


# Add this to conftest.py if not already there
import asyncio

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()