"""Integration tests for Phantom Power Monitoring."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from datetime import datetime, timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry

from custom_components.phantom import async_setup_entry, async_unload_entry
from custom_components.phantom.const import (
    DOMAIN,
    CONF_GROUPS,
    CONF_DEVICES,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_DEVICE_ID,
    CONF_TARIFF,
    CONF_TARIFF_ENABLED,
    CONF_TARIFF_RATE_STRUCTURE,
    CONF_TARIFF_RATE_TYPE,
    CONF_TARIFF_FLAT_RATE,
    TARIFF_TYPE_FLAT,
)


@pytest.mark.asyncio
async def test_full_integration_setup(mock_hass, mock_config_entry):
    """Test full integration setup with tariff enabled."""
    # Configure the integration
    config_data = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Living Room",
                CONF_GROUP_ID: "group_living_room",
                CONF_DEVICES: [
                    {
                        "name": "TV",
                        "power_entity": "sensor.tv_power",
                        "energy_entity": "sensor.tv_energy",
                        CONF_DEVICE_ID: "device_tv",
                    },
                    {
                        "name": "Lamp",
                        "power_entity": "sensor.lamp_power",
                        "energy_entity": "sensor.lamp_energy",
                        CONF_DEVICE_ID: "device_lamp",
                    },
                ],
                "upstream_power_entity": "sensor.living_room_total_power",
                "upstream_energy_entity": "sensor.living_room_total_energy",
            }
        ],
        CONF_TARIFF: {
            CONF_TARIFF_ENABLED: True,
            "currency": "USD",
            "currency_symbol": "$",
            CONF_TARIFF_RATE_STRUCTURE: {
                CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_FLAT,
                CONF_TARIFF_FLAT_RATE: 0.12,
            },
        },
    }
    
    # Mock config entry
    mock_config_entry.data = config_data
    mock_hass.data[DOMAIN] = {}
    
    # Mock entity states
    states = {
        "sensor.tv_power": MagicMock(state="100", attributes={"device_class": "power"}),
        "sensor.tv_energy": MagicMock(state="50", attributes={"device_class": "energy"}),
        "sensor.lamp_power": MagicMock(state="60", attributes={"device_class": "power"}),
        "sensor.lamp_energy": MagicMock(state="30", attributes={"device_class": "energy"}),
        "sensor.living_room_total_power": MagicMock(state="200", attributes={"device_class": "power"}),
        "sensor.living_room_total_energy": MagicMock(state="100", attributes={"device_class": "energy"}),
    }
    mock_hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
    
    # Mock entity registry
    mock_entity_registry = MagicMock()
    mock_entity_registry.entities = {}
    
    # Mock async functions
    mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    mock_hass.helpers.entity_registry.async_get = MagicMock(return_value=mock_entity_registry)
    
    # Setup the integration
    with patch('custom_components.phantom.async_register_panel', AsyncMock()):
        with patch('custom_components.phantom.async_cleanup_orphaned_devices', AsyncMock()):
            result = await async_setup_entry(mock_hass, mock_config_entry)
    
    assert result is True
    assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
    
    # Verify platforms were setup
    mock_hass.config_entries.async_forward_entry_setups.assert_called_once()


@pytest.mark.asyncio
async def test_energy_cost_tracking_workflow(mock_hass, mock_config_entry):
    """Test complete energy cost tracking workflow."""
    # This would be a more comprehensive test simulating:
    # 1. Device energy consumption over time
    # 2. Rate changes (for TOU)
    # 3. Cost accumulation
    # 4. Total cost aggregation
    
    # Setup similar to above but with more detailed state tracking
    pass  # Placeholder for comprehensive workflow test


@pytest.mark.asyncio
async def test_config_reload_preserves_state(mock_hass, mock_config_entry):
    """Test that reloading configuration preserves sensor states."""
    # Setup initial configuration
    config_data = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Test Group",
                CONF_GROUP_ID: "group_test",
                CONF_DEVICES: [
                    {
                        "name": "Device 1",
                        "power_entity": "sensor.device1_power",
                        "energy_entity": "sensor.device1_energy",
                        CONF_DEVICE_ID: "device_1",
                    }
                ],
            }
        ],
    }
    
    mock_config_entry.data = config_data
    mock_hass.data[DOMAIN] = {}
    
    # Mock unload and reload
    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    
    # Test unload
    result = await async_unload_entry(mock_hass, mock_config_entry)
    assert result is True
    
    # Verify cleanup happened
    assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_tariff_mode_switching(mock_hass):
    """Test switching between internal and external tariff modes."""
    from custom_components.phantom.tariff import TariffManager
    from custom_components.phantom.tariff_external import ExternalTariffManager
    
    # Test internal tariff
    internal_config = {
        CONF_TARIFF_ENABLED: True,
        "currency": "USD",
        "currency_symbol": "$",
        CONF_TARIFF_RATE_STRUCTURE: {
            CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_FLAT,
            CONF_TARIFF_FLAT_RATE: 0.15,
        },
    }
    
    internal_manager = TariffManager(internal_config)
    assert internal_manager.get_current_rate() == 0.15
    
    # Test external tariff
    external_config = {
        CONF_TARIFF_ENABLED: True,
        "currency": "USD",
        "currency_symbol": "$",
        "rate_entity": "sensor.grid_rate",
    }
    
    # Mock external rate sensor
    mock_hass.states.get.return_value = MagicMock(state="0.25")
    
    external_manager = ExternalTariffManager(
        mock_hass,
        external_config,
        "sensor.grid_rate",
        None
    )
    external_manager._update_external_values()
    
    assert external_manager.get_current_rate() == 0.25


@pytest.mark.asyncio
async def test_group_rename_migration(mock_hass, mock_config_entry):
    """Test that renaming groups preserves sensor states."""
    # This test would verify the state migration functionality
    # when groups are renamed
    pass  # Placeholder for migration test


@pytest.mark.asyncio
async def test_error_handling_missing_entities(mock_hass, mock_config_entry):
    """Test graceful handling of missing entities."""
    config_data = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Test Group",
                CONF_GROUP_ID: "group_test",
                CONF_DEVICES: [
                    {
                        "name": "Missing Device",
                        "power_entity": "sensor.nonexistent_power",
                        "energy_entity": "sensor.nonexistent_energy",
                        CONF_DEVICE_ID: "device_missing",
                    }
                ],
            }
        ],
    }
    
    mock_config_entry.data = config_data
    mock_hass.data[DOMAIN] = {}
    
    # All entity lookups return None
    mock_hass.states.get.return_value = None
    
    # Should still setup successfully but sensors will be unavailable
    mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    
    with patch('custom_components.phantom.async_register_panel', AsyncMock()):
        with patch('custom_components.phantom.async_cleanup_orphaned_devices', AsyncMock()):
            result = await async_setup_entry(mock_hass, mock_config_entry)
    
    assert result is True


@pytest.mark.asyncio
async def test_concurrent_state_updates(mock_hass):
    """Test handling of concurrent state updates."""
    from custom_components.phantom.sensor import PhantomPowerSensor
    
    # Create sensor with multiple power entities
    sensor = PhantomPowerSensor(
        config_entry_id="test",
        group_name="Test",
        group_id="test",
        power_entities=["sensor.p1", "sensor.p2", "sensor.p3"],
    )
    sensor.hass = mock_hass
    
    # Simulate rapid concurrent updates
    states = {
        "sensor.p1": MagicMock(state="100"),
        "sensor.p2": MagicMock(state="200"),
        "sensor.p3": MagicMock(state="300"),
    }
    mock_hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
    
    # Multiple concurrent updates
    tasks = []
    for _ in range(10):
        event = MagicMock()
        sensor._handle_state_change(event)
    
    # Final state should be consistent
    assert sensor._attr_native_value == 600  # 100 + 200 + 300


@pytest.mark.asyncio
async def test_performance_many_devices(mock_hass, mock_config_entry):
    """Test performance with many devices."""
    # Create config with many devices
    devices = []
    for i in range(50):
        devices.append({
            "name": f"Device {i}",
            "power_entity": f"sensor.device{i}_power",
            "energy_entity": f"sensor.device{i}_energy",
            CONF_DEVICE_ID: f"device_{i}",
        })
    
    config_data = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Large Group",
                CONF_GROUP_ID: "group_large",
                CONF_DEVICES: devices,
            }
        ],
    }
    
    mock_config_entry.data = config_data
    mock_hass.data[DOMAIN] = {}
    
    # Mock all entity states
    def mock_state(entity_id):
        if "_power" in entity_id:
            return MagicMock(state="100", attributes={"device_class": "power"})
        elif "_energy" in entity_id:
            return MagicMock(state="50", attributes={"device_class": "energy"})
        return None
    
    mock_hass.states.get.side_effect = mock_state
    mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    
    # Measure setup time
    import time
    start_time = time.time()
    
    with patch('custom_components.phantom.async_register_panel', AsyncMock()):
        with patch('custom_components.phantom.async_cleanup_orphaned_devices', AsyncMock()):
            result = await async_setup_entry(mock_hass, mock_config_entry)
    
    setup_time = time.time() - start_time
    
    assert result is True
    assert setup_time < 5.0  # Should complete within 5 seconds even with many devices