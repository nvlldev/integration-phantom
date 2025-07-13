"""Tests for power sensor functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers import entity_registry as er

from custom_components.phantom.sensors.power import (
    PhantomPowerSensor,
    PhantomIndividualPowerSensor,
)
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestPhantomPowerSensor:
    """Test the PhantomPowerSensor."""

    @pytest.fixture
    def power_sensor(self, mock_hass):
        """Create a power sensor instance."""
        sensor = PhantomPowerSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            devices=[
                {"name": "Device 1", CONF_DEVICE_ID: "device1_id"},
                {"name": "Device 2", CONF_DEVICE_ID: "device2_id"},
            ],
        )
        sensor.hass = mock_hass
        return sensor

    def test_init(self, power_sensor):
        """Test sensor initialization."""
        assert power_sensor._attr_name == "Power Total"
        assert power_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert power_sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
        assert power_sensor._attr_device_class == SensorDeviceClass.POWER
        assert power_sensor._attr_icon == "mdi:flash"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, power_sensor, mock_hass, mock_entity_registry):
        """Test adding sensor to Home Assistant."""
        power_sensor.async_on_remove = MagicMock()
        power_sensor._update_state = MagicMock()
        power_sensor.async_write_ha_state = MagicMock()
        
        # Mock entity registry with power sensors
        mock_entity_registry.entities = {
            "sensor.device1_power": MagicMock(
                unique_id="device1_id_power",
                domain="sensor",
                platform=DOMAIN,
            ),
            "sensor.device2_power": MagicMock(
                unique_id="device2_id_power",
                domain="sensor",
                platform=DOMAIN,
            ),
        }
        
        with patch("custom_components.phantom.sensors.power.er.async_get", return_value=mock_entity_registry):
            with patch("custom_components.phantom.sensors.power.async_track_state_change_event") as mock_track:
                await power_sensor.async_added_to_hass()
        
        # Should find power entities
        assert power_sensor._power_entities == ["sensor.device1_power", "sensor.device2_power"]
        
        # Should set up tracking
        mock_track.assert_called_once()

    def test_update_state_calculation(self, power_sensor, mock_hass, mock_state):
        """Test power total calculation."""
        power_sensor.hass = mock_hass
        power_sensor._power_entities = ["sensor.device1_power", "sensor.device2_power"]
        power_sensor._attr_native_value = 0
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_power": mock_state("sensor.device1_power", "150.5"),
            "sensor.device2_power": mock_state("sensor.device2_power", "200.3"),
        }.get(entity_id)
        
        power_sensor._update_state()
        
        # Should calculate total: 150.5 + 200.3 = 350.8
        assert power_sensor._attr_native_value == 350.8

    def test_update_state_with_unavailable(self, power_sensor, mock_hass, mock_state):
        """Test update with some sensors unavailable."""
        power_sensor.hass = mock_hass
        power_sensor._power_entities = ["sensor.device1_power", "sensor.device2_power", "sensor.device3_power"]
        
        # Mock states with one unavailable
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_power": mock_state("sensor.device1_power", "100"),
            "sensor.device2_power": mock_state("sensor.device2_power", STATE_UNAVAILABLE),
            "sensor.device3_power": mock_state("sensor.device3_power", "50"),
        }.get(entity_id)
        
        power_sensor._update_state()
        
        # Should only sum available: 100 + 50 = 150
        assert power_sensor._attr_native_value == 150

    def test_handle_state_change(self, power_sensor):
        """Test handling state changes."""
        power_sensor._update_state = MagicMock()
        power_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event
        event = MagicMock(spec=Event)
        event.data = {"new_state": MagicMock()}
        
        power_sensor._handle_state_change(event)
        
        power_sensor._update_state.assert_called_once()
        power_sensor.async_write_ha_state.assert_called_once()


class TestPhantomIndividualPowerSensor:
    """Test the PhantomIndividualPowerSensor."""

    @pytest.fixture
    def individual_power_sensor(self):
        """Create an individual power sensor instance."""
        return PhantomIndividualPowerSensor(
            config_entry_id="test_entry",
            device_name="Test Device",
            device_id="device_123",
        )

    def test_init(self, individual_power_sensor):
        """Test sensor initialization."""
        assert individual_power_sensor._attr_name == "Power"
        assert individual_power_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert individual_power_sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
        assert individual_power_sensor._attr_device_class == SensorDeviceClass.POWER
        assert individual_power_sensor._attr_icon == "mdi:flash"
        assert individual_power_sensor._attr_suggested_display_precision == 1

    def test_unique_id(self, individual_power_sensor):
        """Test unique ID generation."""
        assert individual_power_sensor.unique_id == "device_123_power"

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, individual_power_sensor, mock_hass):
        """Test adding sensor to Home Assistant."""
        individual_power_sensor.hass = mock_hass
        individual_power_sensor._update_state = MagicMock()
        
        # Mock switch entity
        mock_hass.states.get.return_value = MagicMock(
            entity_id="switch.device_123",
            state="on",
            attributes={"current_power_w": 75.5}
        )
        
        with patch("custom_components.phantom.sensors.power.async_track_state_change_event") as mock_track:
            await individual_power_sensor.async_added_to_hass()
        
        # Should set up tracking for the switch
        mock_track.assert_called_once_with(
            mock_hass,
            "switch.device_123",
            individual_power_sensor._handle_state_change
        )
        
        # Should update initial state
        individual_power_sensor._update_state.assert_called_once()

    def test_update_state_from_switch(self, individual_power_sensor, mock_hass):
        """Test updating state from switch attributes."""
        individual_power_sensor.hass = mock_hass
        individual_power_sensor._switch_entity_id = "switch.device_123"
        
        # Mock switch with power attribute
        mock_hass.states.get.return_value = MagicMock(
            state="on",
            attributes={"current_power_w": 123.45}
        )
        
        individual_power_sensor._update_state()
        
        assert individual_power_sensor._attr_native_value == 123.45
        assert individual_power_sensor._attr_available is True

    def test_update_state_switch_off(self, individual_power_sensor, mock_hass):
        """Test updating state when switch is off."""
        individual_power_sensor.hass = mock_hass
        individual_power_sensor._switch_entity_id = "switch.device_123"
        
        # Mock switch off
        mock_hass.states.get.return_value = MagicMock(
            state="off",
            attributes={}
        )
        
        individual_power_sensor._update_state()
        
        assert individual_power_sensor._attr_native_value == 0
        assert individual_power_sensor._attr_available is True

    def test_update_state_no_power_attribute(self, individual_power_sensor, mock_hass):
        """Test updating state when power attribute is missing."""
        individual_power_sensor.hass = mock_hass
        individual_power_sensor._switch_entity_id = "switch.device_123"
        
        # Mock switch without power attribute
        mock_hass.states.get.return_value = MagicMock(
            state="on",
            attributes={}
        )
        
        individual_power_sensor._update_state()
        
        assert individual_power_sensor._attr_native_value is None
        assert individual_power_sensor._attr_available is False

    def test_update_state_switch_unavailable(self, individual_power_sensor, mock_hass):
        """Test updating state when switch is unavailable."""
        individual_power_sensor.hass = mock_hass
        individual_power_sensor._switch_entity_id = "switch.device_123"
        
        # Mock unavailable switch
        mock_hass.states.get.return_value = MagicMock(
            state=STATE_UNAVAILABLE,
            attributes={}
        )
        
        individual_power_sensor._update_state()
        
        assert individual_power_sensor._attr_native_value is None
        assert individual_power_sensor._attr_available is False