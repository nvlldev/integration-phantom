"""Tests for sensor entities."""
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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.sensor import SensorStateClass

from custom_components.phantom.sensors.power import PhantomPowerSensor, PhantomIndividualPowerSensor
from custom_components.phantom.sensors.energy import PhantomEnergySensor, PhantomUtilityMeterSensor
from custom_components.phantom.sensors.cost import (
    PhantomDeviceHourlyCostSensor,
    PhantomDeviceTotalCostSensor,
    PhantomGroupHourlyCostSensor,
    PhantomGroupTotalCostSensor,
    PhantomTouRateSensor,
)
from custom_components.phantom.sensors.upstream import PhantomUpstreamPowerSensor, PhantomUpstreamEnergyMeterSensor
from custom_components.phantom.sensors.remainder import PhantomPowerRemainderSensor, PhantomEnergyRemainderSensor
from custom_components.phantom.sensor import _create_group_sensors
from custom_components.phantom.tariff import TariffManager
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID, CONF_DEVICES


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
        assert power_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert power_sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
        assert power_sensor._attr_unique_id == "group_123_power_total"
        assert len(power_sensor._power_entities) == 2

    @pytest.mark.asyncio
    async def test_state_update_all_available(self, power_sensor, mock_hass, mock_state):
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

    @pytest.mark.asyncio
    async def test_state_update_some_unavailable(self, power_sensor, mock_hass, mock_state):
        """Test state update when some entities are unavailable."""
        power_sensor.hass = mock_hass
        
        # Mock power states with one unavailable
        states = {
            "sensor.device1_power": mock_state("sensor.device1_power", "100.5"),
            "sensor.device2_power": mock_state("sensor.device2_power", STATE_UNAVAILABLE),
        }
        mock_hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
        
        # Update state
        power_sensor._update_state()
        
        assert power_sensor._attr_available is True
        assert power_sensor._attr_native_value == 100.5

    @pytest.mark.asyncio
    async def test_state_update_all_unavailable(self, power_sensor, mock_hass, mock_state):
        """Test state update when all entities are unavailable."""
        power_sensor.hass = mock_hass
        
        # Mock all states as unavailable
        states = {
            "sensor.device1_power": mock_state("sensor.device1_power", STATE_UNAVAILABLE),
            "sensor.device2_power": mock_state("sensor.device2_power", STATE_UNKNOWN),
        }
        mock_hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
        
        # Update state
        power_sensor._update_state()
        
        assert power_sensor._attr_available is False
        assert power_sensor._attr_native_value is None


class TestPhantomUtilityMeterSensor:
    """Test the PhantomUtilityMeterSensor class."""

    @pytest.fixture
    def utility_meter(self, mock_hass):
        """Create a utility meter sensor instance."""
        return PhantomUtilityMeterSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            energy_entity="sensor.device_energy",
        )

    def test_init(self, utility_meter):
        """Test sensor initialization."""
        assert utility_meter._attr_name == "Test Device Energy Meter"
        assert utility_meter._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert utility_meter._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert utility_meter._attr_unique_id == "device_123_utility_meter"

    @pytest.mark.asyncio
    async def test_energy_accumulation(self, utility_meter, mock_hass, mock_state):
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

    @pytest.mark.asyncio
    async def test_energy_reset_detection(self, utility_meter, mock_hass, mock_state):
        """Test detection of energy meter reset."""
        utility_meter.hass = mock_hass
        
        # Set initial value
        utility_meter._last_value = 100.0
        utility_meter._total_consumed = 50.0
        
        # Mock energy reading that decreased (meter reset)
        new_state = mock_state("sensor.device_energy", "5.0")
        old_state = mock_state("sensor.device_energy", "100.0")
        
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state}
        
        # Mock async_write_ha_state
        utility_meter.async_write_ha_state = MagicMock()
        
        # Handle state change
        utility_meter._handle_state_change(event)
        
        # Should add the new value as if starting fresh
        assert utility_meter._total_consumed == 55.0  # 50 + 5
        assert utility_meter._last_value == 5.0

    @pytest.mark.asyncio
    async def test_wh_to_kwh_conversion(self, utility_meter, mock_hass, mock_state):
        """Test Wh to kWh conversion."""
        utility_meter.hass = mock_hass
        
        # Set initial value
        utility_meter._last_value = None
        utility_meter._total_consumed = 0.0
        
        # Mock energy reading in Wh
        new_state = mock_state(
            "sensor.device_energy", 
            "5000.0",
            {"unit_of_measurement": UnitOfEnergy.WATT_HOUR}
        )
        
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": None}
        
        # Mock async_write_ha_state
        utility_meter.async_write_ha_state = MagicMock()
        
        # Handle state change
        utility_meter._handle_state_change(event)
        
        # Should convert to kWh
        assert utility_meter._last_value == 5.0  # 5000 Wh = 5 kWh

    @pytest.mark.asyncio
    async def test_reset_functionality(self, utility_meter, mock_hass, mock_state):
        """Test reset functionality."""
        utility_meter.hass = mock_hass
        
        # Set some accumulated value
        utility_meter._total_consumed = 100.0
        utility_meter._last_value = 50.0
        utility_meter._attr_native_value = 100.0
        
        # Mock current energy state
        current_state = mock_state("sensor.device_energy", "50.0")
        mock_hass.states.get.return_value = current_state
        
        # Mock async_write_ha_state
        utility_meter.async_write_ha_state = MagicMock()
        
        # Reset
        await utility_meter.async_reset()
        
        assert utility_meter._total_consumed == 0.0
        assert utility_meter._attr_native_value == 0.0
        assert utility_meter._last_value == 50.0  # Keeps current reading as baseline


class TestPhantomDeviceTotalCostSensor:
    """Test the PhantomDeviceTotalCostSensor class."""

    @pytest.fixture
    def cost_sensor(self, mock_hass, sample_flat_tariff_config):
        """Create a total cost sensor instance."""
        tariff_manager = TariffManager(sample_flat_tariff_config)
        return PhantomDeviceTotalCostSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            utility_meter_entity="sensor.test_device_utility_meter",
            tariff_manager=tariff_manager,
        )

    def test_init(self, cost_sensor):
        """Test sensor initialization."""
        assert cost_sensor._attr_name == "Test Device Total Cost"
        assert cost_sensor._attr_native_unit_of_measurement == "USD"
        assert cost_sensor._attr_unique_id == "device_123_total_cost"
        assert cost_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING

    @pytest.mark.asyncio
    async def test_cost_calculation_flat_rate(self, cost_sensor, mock_hass, mock_state):
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

    @pytest.mark.asyncio
    async def test_cost_calculation_tou_rate(self, cost_sensor, mock_hass, mock_state, sample_tou_tariff_config):
        """Test cost calculation with TOU rates."""
        # Replace tariff manager with TOU config
        cost_sensor._tariff_manager = TariffManager(sample_tou_tariff_config)
        cost_sensor.hass = mock_hass
        
        # Set initial meter value
        cost_sensor._last_meter_value = 10.0
        cost_sensor._total_cost = 0.0
        
        # Mock meter increase during peak hours (Monday 6 PM)
        with patch('custom_components.phantom.tariff.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 18, 0)  # Peak time
            
            new_state = mock_state("sensor.test_device_utility_meter", "12.0")
            old_state = mock_state("sensor.test_device_utility_meter", "10.0")
            
            event = MagicMock()
            event.data = {"new_state": new_state, "old_state": old_state}
            
            # Mock async_write_ha_state
            cost_sensor.async_write_ha_state = MagicMock()
            
            # Handle state change
            cost_sensor._handle_state_change(event)
            
            # 2 kWh * $0.30/kWh (peak rate) = $0.60
            assert cost_sensor._total_cost == 0.60
            assert cost_sensor._attr_native_value == 0.60

    @pytest.mark.asyncio
    async def test_no_cost_when_meter_decreases(self, cost_sensor, mock_hass, mock_state):
        """Test that no cost is added when meter decreases."""
        cost_sensor.hass = mock_hass
        
        # Set initial values
        cost_sensor._last_meter_value = 20.0
        cost_sensor._total_cost = 3.0
        
        # Mock meter decrease (shouldn't happen in normal operation)
        new_state = mock_state("sensor.test_device_utility_meter", "18.0")
        
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": None}
        
        # Mock async_write_ha_state
        cost_sensor.async_write_ha_state = MagicMock()
        
        # Handle state change
        cost_sensor._handle_state_change(event)
        
        # Cost should not change
        assert cost_sensor._total_cost == 3.0
        assert cost_sensor._last_meter_value == 18.0


class TestPhantomDeviceHourlyCostSensor:
    """Test the PhantomDeviceHourlyCostSensor class."""

    @pytest.fixture
    def cost_per_hour_sensor(self, mock_hass, sample_flat_tariff_config):
        """Create a cost per hour sensor instance."""
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

    def test_init(self, cost_per_hour_sensor):
        """Test sensor initialization."""
        assert cost_per_hour_sensor._attr_name == "Test Device Hourly Cost"
        assert cost_per_hour_sensor._attr_native_unit_of_measurement == "$/h"
        assert cost_per_hour_sensor._attr_unique_id == "device_123_hourly_cost"

    @pytest.mark.asyncio
    async def test_cost_per_hour_calculation(self, cost_per_hour_sensor, mock_hass, mock_state):
        """Test cost per hour calculation."""
        cost_per_hour_sensor.hass = mock_hass
        
        # Mock power reading of 1500W
        power_state = mock_state("sensor.device_power", "1500")
        mock_hass.states.get.return_value = power_state
        
        # Update state
        cost_per_hour_sensor._update_state()
        
        # 1.5 kW * $0.15/kWh = $0.225/h
        assert cost_per_hour_sensor._attr_native_value == 0.225
        assert cost_per_hour_sensor._attr_available is True

    @pytest.mark.asyncio
    async def test_unavailable_when_power_unavailable(self, cost_per_hour_sensor, mock_hass, mock_state):
        """Test sensor unavailable when power is unavailable."""
        cost_per_hour_sensor.hass = mock_hass
        
        # Mock unavailable power
        power_state = mock_state("sensor.device_power", STATE_UNAVAILABLE)
        mock_hass.states.get.return_value = power_state
        
        # Update state
        cost_per_hour_sensor._update_state()
        
        assert cost_per_hour_sensor._attr_available is False
        assert cost_per_hour_sensor._attr_native_value is None


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

    @pytest.mark.asyncio
    async def test_rate_update(self, rate_sensor):
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


@pytest.mark.asyncio
async def test_create_group_sensors(
    mock_hass,
    mock_config_entry,
    sample_group_config,
    sample_flat_tariff_config
):
    """Test creating all sensors for a group."""
    # Mock async_add_entities
    async_add_entities = AsyncMock()
    
    # Set up hass.data structure
    mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: {}}}
    
    # Mock entity states
    states = {
        "sensor.test_power": MagicMock(state="100"),
        "sensor.test_energy": MagicMock(state="50"),
        "sensor.upstream_power": MagicMock(state="150"),
        "sensor.upstream_energy": MagicMock(state="75"),
    }
    mock_hass.states.get.side_effect = lambda entity_id: states.get(entity_id)
    
    # Create sensors
    entities = await _create_group_sensors(
        mock_hass,
        mock_config_entry,
        "Test Group",
        "group_123",
        sample_group_config[CONF_DEVICES],
        "sensor.upstream_power",
        "sensor.upstream_energy",
        sample_flat_tariff_config,
        async_add_entities,
    )
    
    # Check that all expected sensor types were created
    sensor_types = [type(sensor).__name__ for sensor in entities]
    
    assert "PhantomIndividualPowerSensor" in sensor_types
    assert "PhantomUtilityMeterSensor" in sensor_types
    assert "PhantomDeviceHourlyCostSensor" in sensor_types
    assert "PhantomPowerSensor" in sensor_types
    assert "PhantomEnergySensor" in sensor_types
    assert "PhantomGroupHourlyCostSensor" in sensor_types
    assert "PhantomTouRateSensor" in sensor_types
    assert "PhantomUpstreamPowerSensor" in sensor_types
    assert "PhantomUpstreamEnergyMeterSensor" in sensor_types
    assert "PhantomPowerRemainderSensor" in sensor_types
    assert "PhantomEnergyRemainderSensor" in sensor_types
    
    # Verify delayed total cost sensors are scheduled
    assert mock_hass.async_create_task.called