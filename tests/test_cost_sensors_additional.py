"""Tests for additional cost sensor functionality not covered in other test files."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, time

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.phantom.sensors.cost import (
    PhantomDeviceHourlyCostSensor,
    PhantomGroupHourlyCostSensor,
    PhantomTouRateSensor,
    PhantomDeviceTotalCostSensor,
)
from custom_components.phantom.tariff import TariffManager
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestPhantomDeviceHourlyCostSensor:
    """Test the PhantomDeviceHourlyCostSensor."""

    @pytest.fixture
    def mock_tariff_manager(self):
        """Create a mock tariff manager."""
        tariff_manager = MagicMock(spec=TariffManager)
        tariff_manager.currency = "USD"
        tariff_manager.currency_symbol = "$"
        tariff_manager.get_current_rate.return_value = 0.15
        return tariff_manager

    @pytest.fixture
    def device_hourly_cost_sensor(self, mock_tariff_manager):
        """Create a device hourly cost sensor instance."""
        return PhantomDeviceHourlyCostSensor(
            config_entry_id="test_entry",
            device_name="Test Device",
            device_id="device_123",
            tariff_manager=mock_tariff_manager,
        )

    def test_init(self, device_hourly_cost_sensor):
        """Test sensor initialization."""
        assert device_hourly_cost_sensor._attr_name == "Hourly Cost"
        assert device_hourly_cost_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert device_hourly_cost_sensor._attr_native_unit_of_measurement == "USD/h"
        assert device_hourly_cost_sensor._attr_icon == "mdi:cash-clock"
        assert device_hourly_cost_sensor._attr_suggested_display_precision == 3

    def test_unique_id(self, device_hourly_cost_sensor):
        """Test unique ID generation."""
        assert device_hourly_cost_sensor.unique_id == "device_123_hourly_cost"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, device_hourly_cost_sensor, mock_hass):
        """Test adding sensor to Home Assistant."""
        device_hourly_cost_sensor.hass = mock_hass
        device_hourly_cost_sensor._update_state = MagicMock()
        
        with patch("custom_components.phantom.sensors.cost.async_track_state_change_event") as mock_track:
            with patch("custom_components.phantom.sensors.cost.async_track_time_interval") as mock_time_track:
                await device_hourly_cost_sensor.async_added_to_hass()
        
        # Should set up tracking for power sensor
        mock_track.assert_called_once()
        
        # Should set up time interval tracking
        mock_time_track.assert_called_once()
        
        # Should update initial state
        device_hourly_cost_sensor._update_state.assert_called_once()

    def test_update_state_calculation(self, device_hourly_cost_sensor, mock_hass, mock_state):
        """Test hourly cost calculation."""
        device_hourly_cost_sensor.hass = mock_hass
        device_hourly_cost_sensor._power_entity_id = "sensor.device_123_power"
        
        # Mock power sensor
        mock_hass.states.get.return_value = mock_state(
            "sensor.device_123_power",
            "500"  # 500W
        )
        
        device_hourly_cost_sensor._update_state()
        
        # Should calculate: 500W * 0.15$/kWh = 0.075$/h
        assert device_hourly_cost_sensor._attr_native_value == 0.075
        assert device_hourly_cost_sensor._attr_available is True

    def test_update_state_power_unavailable(self, device_hourly_cost_sensor, mock_hass, mock_state):
        """Test update when power sensor is unavailable."""
        device_hourly_cost_sensor.hass = mock_hass
        device_hourly_cost_sensor._power_entity_id = "sensor.device_123_power"
        
        # Mock unavailable power sensor
        mock_hass.states.get.return_value = mock_state(
            "sensor.device_123_power",
            STATE_UNAVAILABLE
        )
        
        device_hourly_cost_sensor._update_state()
        
        assert device_hourly_cost_sensor._attr_native_value is None
        assert device_hourly_cost_sensor._attr_available is False

    def test_extra_state_attributes(self, device_hourly_cost_sensor, mock_tariff_manager):
        """Test extra state attributes."""
        device_hourly_cost_sensor._power_entity_id = "sensor.device_123_power"
        attrs = device_hourly_cost_sensor.extra_state_attributes
        
        assert attrs["currency_symbol"] == "$"
        assert attrs["power_entity"] == "sensor.device_123_power"
        assert attrs["current_rate"] == 0.15


class TestPhantomGroupHourlyCostSensor:
    """Test the PhantomGroupHourlyCostSensor."""

    @pytest.fixture
    def group_hourly_cost_sensor(self, mock_hass, mock_tariff_manager):
        """Create a group hourly cost sensor instance."""
        sensor = PhantomGroupHourlyCostSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            devices=[
                {"name": "Device 1", CONF_DEVICE_ID: "device1_id"},
                {"name": "Device 2", CONF_DEVICE_ID: "device2_id"},
            ],
            tariff_manager=mock_tariff_manager,
        )
        sensor.hass = mock_hass
        return sensor

    def test_init(self, group_hourly_cost_sensor):
        """Test sensor initialization."""
        assert group_hourly_cost_sensor._attr_name == "Hourly Cost"
        assert group_hourly_cost_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert group_hourly_cost_sensor._attr_native_unit_of_measurement == "USD/h"
        assert group_hourly_cost_sensor._attr_icon == "mdi:cash-clock"

    def test_update_state_aggregation(self, group_hourly_cost_sensor, mock_hass, mock_state):
        """Test hourly cost aggregation from devices."""
        group_hourly_cost_sensor._device_hourly_cost_entities = [
            "sensor.device1_hourly_cost",
            "sensor.device2_hourly_cost"
        ]
        
        # Mock device hourly cost sensors
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_hourly_cost": mock_state("sensor.device1_hourly_cost", "0.05"),
            "sensor.device2_hourly_cost": mock_state("sensor.device2_hourly_cost", "0.075"),
        }.get(entity_id)
        
        group_hourly_cost_sensor._update_state()
        
        # Should sum: 0.05 + 0.075 = 0.125
        assert group_hourly_cost_sensor._attr_native_value == 0.125


class TestPhantomTouRateSensor:
    """Test the PhantomTouRateSensor."""

    @pytest.fixture
    def tou_rate_sensor(self, mock_tariff_manager):
        """Create a TOU rate sensor instance."""
        return PhantomTouRateSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            tariff_manager=mock_tariff_manager,
        )

    def test_init(self, tou_rate_sensor):
        """Test sensor initialization."""
        assert tou_rate_sensor._attr_name == "TOU Rate"
        assert tou_rate_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert tou_rate_sensor._attr_native_unit_of_measurement == "USD/kWh"
        assert tou_rate_sensor._attr_icon == "mdi:currency-usd"

    def test_unique_id(self, tou_rate_sensor):
        """Test unique ID generation."""
        assert tou_rate_sensor.unique_id == "group_123_tou_rate"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, tou_rate_sensor, mock_hass):
        """Test adding sensor to Home Assistant."""
        tou_rate_sensor.hass = mock_hass
        tou_rate_sensor._update_state = MagicMock()
        
        with patch("custom_components.phantom.sensors.cost.async_track_time_interval") as mock_track:
            await tou_rate_sensor.async_added_to_hass()
        
        # Should set up time interval tracking
        mock_track.assert_called_once()
        
        # Should update initial state
        tou_rate_sensor._update_state.assert_called_once()

    def test_update_state_rate(self, tou_rate_sensor, mock_tariff_manager):
        """Test updating TOU rate."""
        mock_tariff_manager.get_current_rate.return_value = 0.25
        
        tou_rate_sensor._update_state()
        
        assert tou_rate_sensor._attr_native_value == 0.25
        assert tou_rate_sensor._attr_available is True

    def test_extra_state_attributes(self, tou_rate_sensor, mock_tariff_manager):
        """Test extra state attributes with rate period info."""
        # Mock tariff manager with period info
        mock_tariff_manager.get_current_rate.return_value = 0.15
        mock_tariff_manager.get_current_period_info.return_value = {
            "name": "off-peak",
            "start": time(23, 0),
            "end": time(7, 0),
            "rate": 0.15
        }
        
        tou_rate_sensor._update_state()
        attrs = tou_rate_sensor.extra_state_attributes
        
        assert attrs["currency_symbol"] == "$"
        assert attrs["period_name"] == "off-peak"
        assert attrs["period_start"] == "23:00:00"
        assert attrs["period_end"] == "07:00:00"


class TestPhantomDeviceTotalCostSensor:
    """Test the PhantomDeviceTotalCostSensor."""

    @pytest.fixture
    def device_total_cost_sensor(self, mock_tariff_manager):
        """Create a device total cost sensor instance."""
        return PhantomDeviceTotalCostSensor(
            config_entry_id="test_entry",
            device_name="Test Device",
            device_id="device_123",
            tariff_manager=mock_tariff_manager,
        )

    def test_init(self, device_total_cost_sensor):
        """Test sensor initialization."""
        assert device_total_cost_sensor._attr_name == "Total Cost"
        assert device_total_cost_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert device_total_cost_sensor._attr_native_unit_of_measurement == "USD"
        assert device_total_cost_sensor._attr_icon == "mdi:cash-multiple"
        assert device_total_cost_sensor._attr_suggested_display_precision == 2

    def test_is_restore_entity(self, device_total_cost_sensor):
        """Test that sensor inherits from RestoreEntity."""
        assert isinstance(device_total_cost_sensor, RestoreEntity)

    @pytest.mark.asyncio
    async def test_async_added_to_hass_with_restore(self, device_total_cost_sensor, mock_hass, mock_state):
        """Test adding sensor to Home Assistant with state restoration."""
        device_total_cost_sensor.hass = mock_hass
        device_total_cost_sensor._update_state = MagicMock()
        
        # Mock restored state
        last_state = mock_state("sensor.device_total_cost", "123.45")
        last_state.attributes = {"last_energy_reading": 100.5}
        device_total_cost_sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        with patch("custom_components.phantom.sensors.cost.async_track_state_change_event") as mock_track:
            await device_total_cost_sensor.async_added_to_hass()
        
        # Should restore previous value
        assert device_total_cost_sensor._attr_native_value == 123.45
        assert device_total_cost_sensor._last_energy_reading == 100.5
        assert device_total_cost_sensor._attr_available is True

    def test_update_state_incremental_cost(self, device_total_cost_sensor, mock_hass, mock_state, mock_tariff_manager):
        """Test calculating incremental cost from energy changes."""
        device_total_cost_sensor.hass = mock_hass
        device_total_cost_sensor._utility_meter_entity = "sensor.device_123_meter"
        device_total_cost_sensor._last_energy_reading = 100.0
        device_total_cost_sensor._attr_native_value = 15.0
        
        # Mock energy meter with increased reading
        mock_hass.states.get.return_value = mock_state(
            "sensor.device_123_meter",
            "102.5"  # 2.5 kWh increase
        )
        
        # Mock rate
        mock_tariff_manager.get_current_rate.return_value = 0.20
        
        device_total_cost_sensor._update_state()
        
        # Should add cost: 2.5 kWh * 0.20 $/kWh = 0.50 $
        assert device_total_cost_sensor._attr_native_value == 15.5
        assert device_total_cost_sensor._last_energy_reading == 102.5

    def test_update_state_energy_reset(self, device_total_cost_sensor, mock_hass, mock_state):
        """Test handling energy meter reset."""
        device_total_cost_sensor.hass = mock_hass
        device_total_cost_sensor._utility_meter_entity = "sensor.device_123_meter"
        device_total_cost_sensor._last_energy_reading = 100.0
        
        # Mock energy meter with lower reading (reset)
        mock_hass.states.get.return_value = mock_state(
            "sensor.device_123_meter",
            "5.0"
        )
        
        device_total_cost_sensor._update_state()
        
        # Should update last reading without changing cost
        assert device_total_cost_sensor._last_energy_reading == 5.0

    def test_extra_state_attributes(self, device_total_cost_sensor):
        """Test extra state attributes."""
        device_total_cost_sensor._utility_meter_entity = "sensor.device_123_meter"
        device_total_cost_sensor._last_energy_reading = 50.5
        device_total_cost_sensor._last_update = datetime(2024, 1, 1, 12, 0)
        
        attrs = device_total_cost_sensor.extra_state_attributes
        
        assert attrs["currency_symbol"] == "$"
        assert attrs["utility_meter_entity"] == "sensor.device_123_meter"
        assert attrs["last_energy_reading"] == 50.5
        assert attrs["last_update"] == "2024-01-01T12:00:00"