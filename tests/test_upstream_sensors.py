"""Tests for upstream sensor functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.phantom.sensors.upstream import (
    PhantomUpstreamPowerSensor,
    PhantomUpstreamEnergyMeterSensor,
)
from custom_components.phantom.const import DOMAIN


class TestPhantomUpstreamPowerSensor:
    """Test the PhantomUpstreamPowerSensor."""

    @pytest.fixture
    def upstream_power_sensor(self):
        """Create an upstream power sensor instance."""
        return PhantomUpstreamPowerSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            meter_sensor="sensor.meter_123",
        )

    def test_init(self, upstream_power_sensor):
        """Test sensor initialization."""
        assert upstream_power_sensor._attr_name == "Upstream Power"
        assert upstream_power_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert upstream_power_sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
        assert upstream_power_sensor._attr_device_class == SensorDeviceClass.POWER
        assert upstream_power_sensor._attr_icon == "mdi:transmission-tower-import"
        assert upstream_power_sensor._attr_suggested_display_precision == 1

    def test_unique_id(self, upstream_power_sensor):
        """Test unique ID generation."""
        assert upstream_power_sensor.unique_id == "group_123_upstream_power"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, upstream_power_sensor, mock_hass):
        """Test adding sensor to Home Assistant."""
        upstream_power_sensor.hass = mock_hass
        upstream_power_sensor._update_state = MagicMock()
        
        with patch("custom_components.phantom.sensors.upstream.async_track_state_change_event") as mock_track:
            await upstream_power_sensor.async_added_to_hass()
        
        # Should set up tracking for the meter sensor
        mock_track.assert_called_once_with(
            mock_hass,
            "sensor.meter_123",
            upstream_power_sensor._handle_state_change
        )
        
        # Should update initial state
        upstream_power_sensor._update_state.assert_called_once()

    def test_update_state_from_meter(self, upstream_power_sensor, mock_hass, mock_state):
        """Test updating state from meter sensor."""
        upstream_power_sensor.hass = mock_hass
        
        # Mock meter sensor with power attribute
        mock_hass.states.get.return_value = mock_state(
            "sensor.meter_123",
            "1234.5",
            {"power": 2500.75}
        )
        
        upstream_power_sensor._update_state()
        
        assert upstream_power_sensor._attr_native_value == 2500.75
        assert upstream_power_sensor._attr_available is True

    def test_update_state_no_power_attribute(self, upstream_power_sensor, mock_hass, mock_state):
        """Test updating state when power attribute is missing."""
        upstream_power_sensor.hass = mock_hass
        
        # Mock meter sensor without power attribute
        mock_hass.states.get.return_value = mock_state(
            "sensor.meter_123",
            "1234.5",
            {}
        )
        
        upstream_power_sensor._update_state()
        
        assert upstream_power_sensor._attr_native_value is None
        assert upstream_power_sensor._attr_available is False

    def test_update_state_meter_unavailable(self, upstream_power_sensor, mock_hass, mock_state):
        """Test updating state when meter is unavailable."""
        upstream_power_sensor.hass = mock_hass
        
        # Mock unavailable meter
        mock_hass.states.get.return_value = mock_state(
            "sensor.meter_123",
            STATE_UNAVAILABLE
        )
        
        upstream_power_sensor._update_state()
        
        assert upstream_power_sensor._attr_native_value is None
        assert upstream_power_sensor._attr_available is False

    def test_handle_state_change(self, upstream_power_sensor):
        """Test handling state changes."""
        upstream_power_sensor._update_state = MagicMock()
        upstream_power_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event
        event = MagicMock(spec=Event)
        
        upstream_power_sensor._handle_state_change(event)
        
        upstream_power_sensor._update_state.assert_called_once()
        upstream_power_sensor.async_write_ha_state.assert_called_once()


class TestPhantomUpstreamEnergyMeterSensor:
    """Test the PhantomUpstreamEnergyMeterSensor."""

    @pytest.fixture
    def upstream_energy_sensor(self):
        """Create an upstream energy meter sensor instance."""
        return PhantomUpstreamEnergyMeterSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            meter_sensor="sensor.meter_123",
        )

    def test_init(self, upstream_energy_sensor):
        """Test sensor initialization."""
        assert upstream_energy_sensor._attr_name == "Upstream Energy Meter"
        assert upstream_energy_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert upstream_energy_sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert upstream_energy_sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert upstream_energy_sensor._attr_icon == "mdi:counter"
        assert upstream_energy_sensor._attr_suggested_display_precision == 3

    def test_is_restore_entity(self, upstream_energy_sensor):
        """Test that sensor inherits from RestoreEntity."""
        assert isinstance(upstream_energy_sensor, RestoreEntity)

    @pytest.mark.asyncio
    async def test_async_added_to_hass_with_restore(self, upstream_energy_sensor, mock_hass, mock_state):
        """Test adding sensor to Home Assistant with state restoration."""
        upstream_energy_sensor.hass = mock_hass
        upstream_energy_sensor._update_state = MagicMock()
        
        # Mock restored state
        last_state = mock_state("sensor.upstream_energy", "1234.567")
        upstream_energy_sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        with patch("custom_components.phantom.sensors.upstream.async_track_state_change_event") as mock_track:
            await upstream_energy_sensor.async_added_to_hass()
        
        # Should restore previous value
        assert upstream_energy_sensor._attr_native_value == 1234.567
        assert upstream_energy_sensor._attr_available is True
        
        # Should set up tracking
        mock_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_added_to_hass_invalid_restore(self, upstream_energy_sensor, mock_hass, mock_state):
        """Test state restoration with invalid value."""
        upstream_energy_sensor.hass = mock_hass
        upstream_energy_sensor._update_state = MagicMock()
        
        # Mock restored state with invalid value
        last_state = mock_state("sensor.upstream_energy", "not_a_number")
        upstream_energy_sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        with patch("custom_components.phantom.sensors.upstream.async_track_state_change_event"):
            await upstream_energy_sensor.async_added_to_hass()
        
        # Should not restore invalid value
        assert upstream_energy_sensor._attr_native_value is None

    def test_update_state_from_meter(self, upstream_energy_sensor, mock_hass, mock_state):
        """Test updating state from meter sensor."""
        upstream_energy_sensor.hass = mock_hass
        
        # Mock meter sensor
        mock_hass.states.get.return_value = mock_state(
            "sensor.meter_123",
            "5678.901"
        )
        
        upstream_energy_sensor._update_state()
        
        assert upstream_energy_sensor._attr_native_value == 5678.901
        assert upstream_energy_sensor._attr_available is True

    def test_update_state_invalid_value(self, upstream_energy_sensor, mock_hass, mock_state):
        """Test updating state with invalid value."""
        upstream_energy_sensor.hass = mock_hass
        
        # Mock meter sensor with invalid value
        mock_hass.states.get.return_value = mock_state(
            "sensor.meter_123",
            "invalid"
        )
        
        upstream_energy_sensor._update_state()
        
        assert upstream_energy_sensor._attr_native_value is None
        assert upstream_energy_sensor._attr_available is False

    def test_extra_state_attributes(self, upstream_energy_sensor):
        """Test extra state attributes."""
        upstream_energy_sensor._meter_sensor = "sensor.meter_123"
        attrs = upstream_energy_sensor.extra_state_attributes
        
        assert attrs["meter_sensor"] == "sensor.meter_123"

    def test_handle_state_change_with_new_state(self, upstream_energy_sensor):
        """Test handling state changes with new state."""
        upstream_energy_sensor._update_state = MagicMock()
        upstream_energy_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event with new state
        event = MagicMock(spec=Event)
        event.data = {"new_state": MagicMock()}
        
        upstream_energy_sensor._handle_state_change(event)
        
        upstream_energy_sensor._update_state.assert_called_once()
        upstream_energy_sensor.async_write_ha_state.assert_called_once()

    def test_handle_state_change_no_new_state(self, upstream_energy_sensor):
        """Test handling state changes without new state."""
        upstream_energy_sensor._update_state = MagicMock()
        upstream_energy_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event without new state
        event = MagicMock(spec=Event)
        event.data = {"new_state": None}
        
        upstream_energy_sensor._handle_state_change(event)
        
        # Should not update
        upstream_energy_sensor._update_state.assert_not_called()
        upstream_energy_sensor.async_write_ha_state.assert_not_called()