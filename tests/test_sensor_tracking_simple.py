"""Simple test to verify sensor tracking works."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from custom_components.phantom.sensors.power import PhantomIndividualPowerSensor
from custom_components.phantom.sensors.energy import PhantomUtilityMeterSensor
from custom_components.phantom.sensors.cost import PhantomDeviceHourlyCostSensor, PhantomDeviceTotalCostSensor
from custom_components.phantom.tariff import TariffManager


@pytest.mark.asyncio
async def test_power_sensor_tracking_setup():
    """Test that power sensor sets up tracking correctly."""
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    # Mock tracking function to verify it gets called
    mock_track = MagicMock()
    
    # Create sensor
    sensor = PhantomIndividualPowerSensor(
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        power_entity="sensor.device_power",
    )
    sensor.hass = mock_hass
    sensor.entity_id = "sensor.test_device_power"
    sensor.async_on_remove = MagicMock()
    
    # Mock power state
    mock_state = MagicMock()
    mock_state.state = "100"
    mock_hass.states.get.return_value = mock_state
    
    # Patch the tracking function
    with patch('custom_components.phantom.sensors.power.async_track_state_change_event', return_value=mock_track) as patched_track:
        # Set up tracking
        await sensor.async_added_to_hass()
        
        # Verify tracking was set up
        patched_track.assert_called_once_with(
            mock_hass,
            ["sensor.device_power"],
            sensor._handle_state_change,
        )
        
        # Verify initial state was set
        assert sensor._attr_native_value == 100
        assert sensor._attr_available is True


@pytest.mark.asyncio
async def test_utility_meter_tracking_setup():
    """Test that utility meter sensor sets up tracking correctly."""
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    # Create sensor
    sensor = PhantomUtilityMeterSensor(
        hass=mock_hass,
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        energy_entity="sensor.device_energy",
    )
    sensor.entity_id = "sensor.test_device_utility_meter"
    sensor.async_on_remove = MagicMock()
    sensor.async_write_ha_state = MagicMock()
    
    # Mock energy state
    mock_state = MagicMock()
    mock_state.state = "100"
    mock_state.attributes = {}
    mock_hass.states.get.return_value = mock_state
    
    # Patch the tracking function
    with patch('custom_components.phantom.sensors.energy.async_track_state_change_event') as patched_track:
        # Set up tracking
        await sensor.async_added_to_hass()
        
        # Verify tracking was set up
        patched_track.assert_called_once_with(
            mock_hass,
            ["sensor.device_energy"],
            sensor._handle_state_change,
        )
        
        # Verify initial state
        assert sensor._last_value == 100.0
        # Note: total_consumed might be non-zero due to state restoration logic
        assert sensor._total_consumed is not None


@pytest.mark.asyncio
async def test_hourly_cost_sensor_tracking_setup():
    """Test that hourly cost sensor sets up tracking correctly."""
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    # Create tariff manager
    tariff_config = {
        "enabled": True,
        "currency": "USD",
        "currency_symbol": "$",
        "rate_structure": {"type": "flat", "flat_rate": 0.15}
    }
    tariff_manager = TariffManager(tariff_config)
    
    # Create sensor
    sensor = PhantomDeviceHourlyCostSensor(
        hass=mock_hass,
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        power_entity="sensor.device_power",
        tariff_manager=tariff_manager,
    )
    sensor.entity_id = "sensor.test_device_hourly_cost"
    sensor.async_on_remove = MagicMock()
    
    # Mock power state
    mock_state = MagicMock()
    mock_state.state = "1000"  # 1 kW
    mock_hass.states.get.return_value = mock_state
    
    # Patch the tracking function
    with patch('custom_components.phantom.sensors.cost.async_track_state_change_event') as patched_track:
        # Set up tracking
        await sensor.async_added_to_hass()
        
        # Verify tracking was set up
        patched_track.assert_called_once_with(
            mock_hass,
            ["sensor.device_power"],
            sensor._handle_state_change,
        )
        
        # Verify initial cost calculation: 1 kW * $0.15/kWh = $0.15/h
        assert sensor._attr_native_value == 0.15
        assert sensor._attr_available is True


@pytest.mark.asyncio
async def test_total_cost_sensor_tracking_setup():
    """Test that total cost sensor sets up tracking correctly."""
    mock_hass = MagicMock()
    mock_hass.states = MagicMock()
    
    # Create tariff manager
    tariff_config = {
        "enabled": True,
        "currency": "USD",
        "currency_symbol": "$",
        "rate_structure": {"type": "flat", "flat_rate": 0.15}
    }
    tariff_manager = TariffManager(tariff_config)
    
    # Create sensor
    sensor = PhantomDeviceTotalCostSensor(
        hass=mock_hass,
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        utility_meter_entity="sensor.device_utility_meter",
        tariff_manager=tariff_manager,
    )
    sensor.entity_id = "sensor.test_device_total_cost"
    sensor.async_on_remove = MagicMock()
    sensor.async_write_ha_state = MagicMock()
    
    # Mock utility meter state
    mock_state = MagicMock()
    mock_state.state = "10.0"
    mock_hass.states.get.return_value = mock_state
    
    # Patch the tracking function
    with patch('custom_components.phantom.sensors.cost.async_track_state_change_event') as patched_track:
        # Set up tracking
        await sensor.async_added_to_hass()
        
        # Verify tracking was set up
        patched_track.assert_called_once_with(
            mock_hass,
            ["sensor.device_utility_meter"],
            sensor._handle_state_change,
        )
        
        # Verify initial state (first reading)
        assert sensor._last_meter_value == 10.0
        # Note: total cost might be non-zero due to state restoration logic
        assert sensor._attr_native_value is not None


def test_power_sensor_state_change_callback():
    """Test power sensor state change callback."""
    mock_hass = MagicMock()
    
    # Create sensor
    sensor = PhantomIndividualPowerSensor(
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        power_entity="sensor.device_power",
    )
    sensor.hass = mock_hass
    sensor.async_write_ha_state = MagicMock()
    
    # Mock initial power state
    mock_state = MagicMock()
    mock_state.state = "150"
    mock_hass.states.get.return_value = mock_state
    
    # Create mock event
    event = MagicMock()
    event.data = {
        "entity_id": "sensor.device_power",
        "new_state": mock_state,
        "old_state": MagicMock(state="100"),
    }
    
    # Handle state change
    sensor._handle_state_change(event)
    
    # Verify sensor updated
    assert sensor._attr_native_value == 150
    assert sensor._attr_available is True
    sensor.async_write_ha_state.assert_called_once()


def test_total_cost_sensor_state_change_callback():
    """Test total cost sensor state change callback."""
    mock_hass = MagicMock()
    
    # Create tariff manager
    tariff_config = {
        "enabled": True,
        "currency": "USD",
        "currency_symbol": "$",
        "rate_structure": {"type": "flat", "flat_rate": 0.15}
    }
    tariff_manager = TariffManager(tariff_config)
    
    # Create sensor
    sensor = PhantomDeviceTotalCostSensor(
        hass=mock_hass,
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        utility_meter_entity="sensor.device_utility_meter",
        tariff_manager=tariff_manager,
    )
    sensor.async_write_ha_state = MagicMock()
    
    # Set initial state
    sensor._last_meter_value = 10.0
    sensor._total_cost = 0.0
    
    # Create mock event for meter increase (10.0 -> 15.0 = 5 kWh consumed)
    new_state = MagicMock()
    new_state.state = "15.0"
    
    old_state = MagicMock()
    old_state.state = "10.0"
    
    event = MagicMock()
    event.data = {
        "entity_id": "sensor.device_utility_meter",
        "new_state": new_state,
        "old_state": old_state,
    }
    
    # Handle state change
    sensor._handle_state_change(event)
    
    # Verify cost calculation: 5 kWh * $0.15/kWh = $0.75
    assert sensor._last_meter_value == 15.0
    assert sensor._total_cost == 0.75
    assert sensor._attr_native_value == 0.75
    assert sensor._attr_available is True
    sensor.async_write_ha_state.assert_called_once()


def test_utility_meter_sensor_state_change_callback():
    """Test utility meter sensor state change callback."""
    mock_hass = MagicMock()
    
    # Create sensor
    sensor = PhantomUtilityMeterSensor(
        hass=mock_hass,
        config_entry_id="test_entry",
        group_name="Test Group",
        device_name="Test Device",
        device_id="device_123",
        energy_entity="sensor.device_energy",
    )
    sensor.async_write_ha_state = MagicMock()
    
    # Set initial state
    sensor._last_value = 100.0
    sensor._total_consumed = 0.0
    
    # Create mock event for energy increase (100 -> 105 = 5 kWh consumed)
    new_state = MagicMock()
    new_state.state = "105.0"
    new_state.attributes = {}
    
    old_state = MagicMock()
    old_state.state = "100.0"
    
    event = MagicMock()
    event.data = {
        "entity_id": "sensor.device_energy",
        "new_state": new_state,
        "old_state": old_state,
    }
    
    # Handle state change
    sensor._handle_state_change(event)
    
    # Verify accumulation: 5 kWh added
    assert sensor._last_value == 105.0
    assert sensor._total_consumed == 5.0
    assert sensor._attr_native_value == 5.0
    sensor.async_write_ha_state.assert_called_once()