"""Common tests for sensor behavior that applies to multiple sensor types."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import asyncio

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.phantom.sensors.remainder import (
    PhantomPowerRemainderSensor,
    PhantomEnergyRemainderSensor,
)
from custom_components.phantom.sensors.remainder_cost import PhantomCostRemainderSensor
from custom_components.phantom.sensors.energy import PhantomEnergySensor
from custom_components.phantom.sensors.cost import PhantomGroupTotalCostSensor
from custom_components.phantom.tariff import TariffManager
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestCommonSensorBehavior:
    """Test common behavior across all sensor types."""

    @pytest.fixture
    def mock_tariff_manager(self):
        """Create a mock tariff manager."""
        tariff_manager = MagicMock(spec=TariffManager)
        tariff_manager.currency = "USD"
        tariff_manager.currency_symbol = "$"
        return tariff_manager

    def create_sensor(self, sensor_type, mock_hass, mock_tariff_manager):
        """Create a sensor instance based on type."""
        if sensor_type == "power_remainder":
            return PhantomPowerRemainderSensor(
                config_entry_id="test_entry",
                group_name="Test Group",
                group_id="group_123",
                upstream_entity="sensor.upstream",
                power_entities=["sensor.device1", "sensor.device2"],
            )
        elif sensor_type == "energy_remainder":
            sensor = PhantomEnergyRemainderSensor(
                hass=mock_hass,
                config_entry_id="test_entry",
                group_name="Test Group",
                group_id="group_123",
                upstream_entity="sensor.upstream",
                devices=[{"name": "Device 1", CONF_DEVICE_ID: "device1_id"}],
            )
            sensor.hass = mock_hass
            return sensor
        elif sensor_type == "cost_remainder":
            return PhantomCostRemainderSensor(
                hass=mock_hass,
                config_entry_id="test_entry",
                group_name="Test Group",
                group_id="group_123",
                upstream_cost_entity="sensor.upstream",
                device_cost_entities=["sensor.device1", "sensor.device2"],
                currency="USD",
                currency_symbol="$",
            )
        elif sensor_type == "energy_total":
            sensor = PhantomEnergySensor(
                hass=mock_hass,
                config_entry_id="test_entry",
                group_name="Test Group",
                group_id="group_123",
                devices=[{"name": "Device 1", CONF_DEVICE_ID: "device1_id"}],
            )
            sensor.hass = mock_hass
            return sensor
        elif sensor_type == "cost_total":
            sensor = PhantomGroupTotalCostSensor(
                hass=mock_hass,
                config_entry_id="test_entry",
                group_name="Test Group",
                group_id="group_123",
                devices=[{"name": "Device 1", CONF_DEVICE_ID: "device1_id"}],
                tariff_manager=mock_tariff_manager,
            )
            sensor.hass = mock_hass
            return sensor

    @pytest.mark.parametrize("sensor_type", [
        "power_remainder",
        "energy_remainder", 
        "cost_remainder",
        "energy_total",
        "cost_total",
    ])
    def test_handle_state_change(self, sensor_type, mock_hass, mock_tariff_manager):
        """Test handling state changes for all sensor types."""
        sensor = self.create_sensor(sensor_type, mock_hass, mock_tariff_manager)
        sensor.hass = mock_hass
        sensor._update_state = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        
        # Create mock event with new state
        event = MagicMock(spec=Event)
        event.data = {"new_state": MagicMock()}
        
        sensor._handle_state_change(event)
        
        sensor._update_state.assert_called_once()
        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.parametrize("sensor_type", [
        "power_remainder",
        "energy_remainder",
        "cost_remainder", 
        "energy_total",
        "cost_total",
    ])
    def test_handle_state_change_no_new_state(self, sensor_type, mock_hass, mock_tariff_manager):
        """Test handling state changes when new state is None."""
        sensor = self.create_sensor(sensor_type, mock_hass, mock_tariff_manager)
        sensor.hass = mock_hass
        sensor._update_state = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        
        # Create mock event without new state
        event = MagicMock(spec=Event)
        event.data = {"new_state": None}
        
        sensor._handle_state_change(event)
        
        # Should not update
        sensor._update_state.assert_not_called()
        sensor.async_write_ha_state.assert_not_called()

    @pytest.mark.parametrize("sensor_type,has_delayed_setup", [
        ("energy_remainder", True),
        ("energy_total", True),
        ("cost_total", True),
    ])
    def test_update_state_before_setup(self, sensor_type, has_delayed_setup, mock_hass, mock_tariff_manager):
        """Test update state before setup is complete for sensors with delayed setup."""
        sensor = self.create_sensor(sensor_type, mock_hass, mock_tariff_manager)
        sensor.hass = mock_hass
        
        if has_delayed_setup:
            sensor._setup_delayed = False
            initial_value = sensor._attr_native_value
            sensor._update_state()
            
            # Should not update anything
            assert sensor._attr_native_value == initial_value

    @pytest.mark.parametrize("sensor_type,expected_value", [
        ("power_remainder", 45.5),
        ("energy_remainder", 150.5),
        ("cost_remainder", -2.25),
        ("energy_total", 150.5),
        ("cost_total", 99.99),
    ])
    @pytest.mark.asyncio
    async def test_state_restoration(self, sensor_type, expected_value, mock_hass, mock_state, mock_tariff_manager):
        """Test that sensors restore their previous state after restart."""
        sensor = self.create_sensor(sensor_type, mock_hass, mock_tariff_manager)
        sensor.hass = mock_hass
        sensor.async_on_remove = MagicMock()
        sensor._update_state = MagicMock()
        
        # For sensors with delayed setup
        if hasattr(sensor, '_delayed_setup'):
            sensor._delayed_setup = AsyncMock()
        
        # Mock restored state
        last_state = mock_state(f"sensor.test_{sensor.__class__.__name__}", str(expected_value))
        sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        # Mock async_create_task
        if hasattr(sensor, '_delayed_setup'):
            mock_hass.async_create_task = AsyncMock()
        
        with patch("custom_components.phantom.sensors.remainder.async_track_state_change_event"):
            with patch("custom_components.phantom.sensors.remainder_cost.async_track_state_change_event"):
                await sensor.async_added_to_hass()
        
        # Should restore previous value
        assert sensor._attr_native_value == expected_value
        if sensor_type in ["power_remainder", "cost_remainder"]:
            assert sensor._attr_available is True

    @pytest.mark.parametrize("sensor_type", [
        "power_remainder",
        "energy_remainder",
        "cost_remainder",
        "energy_total", 
        "cost_total",
    ])
    @pytest.mark.asyncio
    async def test_state_restoration_invalid(self, sensor_type, mock_hass, mock_state, mock_tariff_manager):
        """Test state restoration with invalid state."""
        sensor = self.create_sensor(sensor_type, mock_hass, mock_tariff_manager)
        sensor.hass = mock_hass
        sensor.async_on_remove = MagicMock()
        sensor._update_state = MagicMock()
        
        # For sensors with delayed setup
        if hasattr(sensor, '_delayed_setup'):
            sensor._delayed_setup = AsyncMock()
        
        # Mock restored state with invalid value
        last_state = mock_state("sensor.test", "not_a_number")
        sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        # Mock async_create_task
        if hasattr(sensor, '_delayed_setup'):
            mock_hass.async_create_task = AsyncMock()
        
        with patch("custom_components.phantom.sensors.remainder.async_track_state_change_event"):
            with patch("custom_components.phantom.sensors.remainder_cost.async_track_state_change_event"):
                await sensor.async_added_to_hass()
        
        # Should not restore invalid value
        if sensor_type in ["energy_total"]:
            assert sensor._attr_native_value == 0.0
        else:
            assert sensor._attr_native_value is None

    @pytest.mark.parametrize("sensor_type", [
        "power_remainder",
        "energy_remainder", 
        "cost_remainder",
        "energy_total",
        "cost_total",
    ])
    @pytest.mark.asyncio
    async def test_state_restoration_unavailable(self, sensor_type, mock_hass, mock_state, mock_tariff_manager):
        """Test state restoration with unavailable state."""
        sensor = self.create_sensor(sensor_type, mock_hass, mock_tariff_manager)
        sensor.hass = mock_hass
        sensor.async_on_remove = MagicMock()
        sensor._update_state = MagicMock()
        
        # For sensors with delayed setup
        if hasattr(sensor, '_delayed_setup'):
            sensor._delayed_setup = AsyncMock()
        
        # Mock restored state as unavailable
        last_state = mock_state("sensor.test", STATE_UNAVAILABLE)
        sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        # Mock async_create_task
        if hasattr(sensor, '_delayed_setup'):
            mock_hass.async_create_task = AsyncMock()
        
        with patch("custom_components.phantom.sensors.remainder.async_track_state_change_event"):
            with patch("custom_components.phantom.sensors.remainder_cost.async_track_state_change_event"):
                await sensor.async_added_to_hass()
        
        # Should not restore unavailable state
        if sensor_type in ["energy_total"]:
            assert sensor._attr_native_value == 0.0
        else:
            assert sensor._attr_native_value is None