"""Tests for sensor entities - fixed version."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import asyncio

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.components.sensor import SensorStateClass

from custom_components.phantom.sensors.power import PhantomPowerSensor
from custom_components.phantom.sensors.energy import PhantomUtilityMeterSensor
from custom_components.phantom.sensors.cost import (
    PhantomDeviceTotalCostSensor,
    PhantomDeviceHourlyCostSensor,
    PhantomTouRateSensor,
)
from custom_components.phantom.tariff import TariffManager
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestPhantomPowerSensor:
    """Test the PhantomPowerSensor class."""

    @pytest.fixture
    def power_sensor(self):
        """Create a power sensor instance."""
        return PhantomPowerSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            power_entities=["sensor.device1_power", "sensor.device2_power"],
        )

    def test_init(self, power_sensor):
        """Test sensor initialization."""
        assert power_sensor._attr_name == "Power Total"
        assert power_sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
        assert power_sensor._attr_unique_id == "group_123_power_total"
        assert len(power_sensor._power_entities) == 2

    def test_state_update_all_available(self, power_sensor, mock_hass, mock_state):
        """Test state update when all entities are available."""
        power_sensor.hass = mock_hass
        
        # Mock power states
        states = {
            "sensor.device1_power": mock_state("sensor.device1_power", "100.5"),
            "sensor.device2_power": mock_state("sensor.device2_power", "50.3"),
        }
        mock_hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
        
        # Update state
        power_sensor._update_state()
        
        assert power_sensor._attr_available is True
        assert power_sensor._attr_native_value == 150.8  # 100.5 + 50.3


class TestPhantomUtilityMeterSensor:
    """Test the PhantomUtilityMeterSensor class."""

    @pytest.fixture
    def utility_meter(self, mock_hass):
        """Create a utility meter sensor instance."""
        sensor = PhantomUtilityMeterSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            energy_entity="sensor.device_energy",
        )
        # Mock entity_id for state writing
        sensor.entity_id = "sensor.test_device_utility_meter"
        return sensor

    def test_init(self, utility_meter):
        """Test sensor initialization."""
        assert utility_meter._attr_name == "Test Device Energy Meter"
        assert utility_meter._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert utility_meter._attr_unique_id == "device_123_utility_meter"

    def test_energy_accumulation(self, utility_meter, mock_hass, mock_state):
        """Test energy accumulation over time."""
        utility_meter.hass = mock_hass
        
        # Set initial value
        utility_meter._last_value = 100.0
        utility_meter._total_consumed = 10.0
        
        # Mock new energy reading (increased by 5 kWh)
        new_state = mock_state("sensor.device_energy", "105.0")
        old_state = mock_state("sensor.device_energy", "100.0")
        
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state}
        
        # Mock async_write_ha_state
        utility_meter.async_write_ha_state = MagicMock()
        
        # Handle state change
        utility_meter._handle_state_change(event)
        
        assert utility_meter._total_consumed == 15.0  # 10 + 5
        assert utility_meter._last_value == 105.0
        assert utility_meter._attr_native_value == 15.0


class TestPhantomDeviceTotalCostSensor:
    """Test the PhantomDeviceTotalCostSensor class."""

    @pytest.fixture
    def cost_sensor(self, mock_hass, sample_flat_tariff_config):
        """Create a total cost sensor instance."""
        tariff_manager = TariffManager(sample_flat_tariff_config)
        sensor = PhantomDeviceTotalCostSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            utility_meter_entity="sensor.test_device_utility_meter",
            tariff_manager=tariff_manager,
        )
        # Mock entity_id for state writing
        sensor.entity_id = "sensor.test_device_total_cost"
        return sensor

    def test_init(self, cost_sensor):
        """Test sensor initialization."""
        assert cost_sensor._attr_name == "Test Device Total Cost"
        assert cost_sensor._attr_native_unit_of_measurement == "USD"
        assert cost_sensor._attr_unique_id == "device_123_total_cost"

    def test_cost_calculation_flat_rate(self, cost_sensor, mock_hass, mock_state):
        """Test cost calculation with flat rate."""
        cost_sensor.hass = mock_hass
        
        # Set initial meter value
        cost_sensor._last_meter_value = 10.0
        cost_sensor._total_cost = 1.5  # Already spent $1.50
        
        # Mock meter increase by 5 kWh
        new_state = mock_state("sensor.test_device_utility_meter", "15.0")
        old_state = mock_state("sensor.test_device_utility_meter", "10.0")
        
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state}
        
        # Mock async_write_ha_state
        cost_sensor.async_write_ha_state = MagicMock()
        
        # Handle state change
        cost_sensor._handle_state_change(event)
        
        # 5 kWh * $0.15/kWh = $0.75
        assert cost_sensor._total_cost == 2.25  # 1.5 + 0.75
        assert cost_sensor._attr_native_value == 2.25


class TestPhantomDeviceHourlyCostSensor:
    """Test the PhantomDeviceHourlyCostSensor class."""

    @pytest.fixture
    def hourly_cost_sensor(self, mock_hass, sample_flat_tariff_config):
        """Create a hourly cost sensor instance."""
        tariff_manager = TariffManager(sample_flat_tariff_config)
        return PhantomDeviceHourlyCostSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            power_entity="sensor.device_power",
            tariff_manager=tariff_manager,
        )

    def test_init(self, hourly_cost_sensor):
        """Test sensor initialization."""
        assert hourly_cost_sensor._attr_name == "Test Device Hourly Cost"
        assert hourly_cost_sensor._attr_native_unit_of_measurement == "$/h"
        assert hourly_cost_sensor._attr_unique_id == "device_123_hourly_cost"

    def test_cost_per_hour_calculation(self, hourly_cost_sensor, mock_hass, mock_state):
        """Test cost per hour calculation."""
        hourly_cost_sensor.hass = mock_hass
        
        # Mock power reading of 1500W
        power_state = mock_state("sensor.device_power", "1500")
        mock_hass.states.get.return_value = power_state
        
        # Update state
        hourly_cost_sensor._update_state()
        
        # 1.5 kW * $0.15/kWh = $0.225/h
        assert hourly_cost_sensor._attr_native_value == 0.225
        assert hourly_cost_sensor._attr_available is True


class TestPhantomTouRateSensor:
    """Test the PhantomTouRateSensor class."""

    @pytest.fixture
    def rate_sensor(self, sample_tou_tariff_config):
        """Create a TOU rate sensor instance."""
        tariff_manager = TariffManager(sample_tou_tariff_config)
        return PhantomTouRateSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            tariff_manager=tariff_manager,
        )

    def test_init(self, rate_sensor):
        """Test sensor initialization."""
        assert rate_sensor._attr_name == "Current Electricity Rate"
        assert rate_sensor._attr_native_unit_of_measurement == "$/kWh"
        assert rate_sensor._attr_unique_id == "group_123_current_rate"

    def test_rate_update(self, rate_sensor):
        """Test rate updates."""
        # Test during peak hours
        with patch('custom_components.phantom.tariff.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 18, 0)  # Peak time
            rate_sensor._update_state()
            assert rate_sensor._attr_native_value == 0.30
            
        # Test during off-peak hours
        with patch('custom_components.phantom.tariff.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 22, 0)  # Off-peak
            rate_sensor._update_state()
            assert rate_sensor._attr_native_value == 0.10