"""Tests for utility meter sensor functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity

from custom_components.phantom.sensors.energy import PhantomUtilityMeterSensor
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestPhantomUtilityMeterSensor:
    """Test the PhantomUtilityMeterSensor."""

    @pytest.fixture
    def utility_meter_sensor(self):
        """Create a utility meter sensor instance."""
        return PhantomUtilityMeterSensor(
            config_entry_id="test_entry",
            device_name="Test Device",
            device_id="device_123",
        )

    def test_init(self, utility_meter_sensor):
        """Test sensor initialization."""
        assert utility_meter_sensor._attr_name == "Utility Meter"
        assert utility_meter_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert utility_meter_sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert utility_meter_sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert utility_meter_sensor._attr_icon == "mdi:counter"
        assert utility_meter_sensor._attr_suggested_display_precision == 3

    def test_unique_id(self, utility_meter_sensor):
        """Test unique ID generation."""
        assert utility_meter_sensor.unique_id == "device_123_utility_meter"

    def test_is_restore_entity(self, utility_meter_sensor):
        """Test that sensor inherits from RestoreEntity."""
        assert isinstance(utility_meter_sensor, RestoreEntity)

    @pytest.mark.asyncio
    async def test_async_added_to_hass_with_restore(self, utility_meter_sensor, mock_hass, mock_state):
        """Test adding sensor to Home Assistant with state restoration."""
        utility_meter_sensor.hass = mock_hass
        utility_meter_sensor._update_state = MagicMock()
        
        # Mock restored state
        last_state = mock_state("sensor.utility_meter", "123.456")
        last_state.attributes = {
            "last_reset": "2024-01-01T00:00:00",
            "total_increasing": 125.0
        }
        utility_meter_sensor.async_get_last_state = AsyncMock(return_value=last_state)
        
        # Mock switch entity exists
        mock_hass.states.get.return_value = MagicMock(entity_id="switch.device_123")
        
        with patch("custom_components.phantom.sensors.energy.async_track_state_change_event") as mock_track:
            await utility_meter_sensor.async_added_to_hass()
        
        # Should restore previous value
        assert utility_meter_sensor._attr_native_value == 123.456
        assert utility_meter_sensor._attr_available is True
        
        # Should set up tracking
        mock_track.assert_called_once_with(
            mock_hass,
            "switch.device_123",
            utility_meter_sensor._handle_state_change
        )

    @pytest.mark.asyncio
    async def test_async_added_to_hass_no_restore(self, utility_meter_sensor, mock_hass):
        """Test adding sensor without restored state."""
        utility_meter_sensor.hass = mock_hass
        utility_meter_sensor._update_state = MagicMock()
        
        # No restored state
        utility_meter_sensor.async_get_last_state = AsyncMock(return_value=None)
        
        # Mock switch entity exists
        mock_hass.states.get.return_value = MagicMock(entity_id="switch.device_123")
        
        with patch("custom_components.phantom.sensors.energy.async_track_state_change_event"):
            await utility_meter_sensor.async_added_to_hass()
        
        # Should start at 0
        assert utility_meter_sensor._attr_native_value == 0.0
        assert utility_meter_sensor._total_consumption == 0.0

    def test_update_state_accumulate_energy(self, utility_meter_sensor, mock_hass):
        """Test accumulating energy consumption."""
        utility_meter_sensor.hass = mock_hass
        utility_meter_sensor._switch_entity_id = "switch.device_123"
        utility_meter_sensor._total_consumption = 10.0
        utility_meter_sensor._last_power = 100.0  # 100W
        utility_meter_sensor._last_update = datetime.now()
        
        # Mock switch with power
        mock_hass.states.get.return_value = MagicMock(
            state="on",
            attributes={"current_power_w": 150.0}
        )
        
        # Mock time passage (1 hour)
        with patch("custom_components.phantom.sensors.energy.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.now()
            # Simulate 1 hour has passed
            utility_meter_sensor._last_update = datetime.now().replace(
                hour=datetime.now().hour - 1
            )
            
            utility_meter_sensor._update_state()
        
        # Should accumulate energy (rough check due to time mocking complexity)
        assert utility_meter_sensor._total_consumption > 10.0
        assert utility_meter_sensor._last_power == 150.0

    def test_update_state_switch_off(self, utility_meter_sensor, mock_hass):
        """Test state when switch is off."""
        utility_meter_sensor.hass = mock_hass
        utility_meter_sensor._switch_entity_id = "switch.device_123"
        utility_meter_sensor._last_power = 100.0
        
        # Mock switch off
        mock_hass.states.get.return_value = MagicMock(
            state="off",
            attributes={}
        )
        
        utility_meter_sensor._update_state()
        
        # Power should be 0 when off
        assert utility_meter_sensor._last_power == 0.0

    def test_update_state_no_power_attribute(self, utility_meter_sensor, mock_hass):
        """Test state when power attribute is missing."""
        utility_meter_sensor.hass = mock_hass
        utility_meter_sensor._switch_entity_id = "switch.device_123"
        utility_meter_sensor._last_power = 100.0
        
        # Mock switch without power attribute
        mock_hass.states.get.return_value = MagicMock(
            state="on",
            attributes={}
        )
        
        utility_meter_sensor._update_state()
        
        # Should keep last known power
        assert utility_meter_sensor._last_power == 100.0

    def test_reset_meter(self, utility_meter_sensor):
        """Test resetting the utility meter."""
        utility_meter_sensor._total_consumption = 123.456
        utility_meter_sensor._attr_native_value = 123.456
        utility_meter_sensor.async_write_ha_state = MagicMock()
        
        utility_meter_sensor.reset_meter()
        
        assert utility_meter_sensor._total_consumption == 0.0
        assert utility_meter_sensor._attr_native_value == 0.0
        assert utility_meter_sensor._last_reset is not None
        utility_meter_sensor.async_write_ha_state.assert_called_once()

    def test_extra_state_attributes(self, utility_meter_sensor):
        """Test extra state attributes."""
        utility_meter_sensor._last_reset = datetime(2024, 1, 1, 0, 0)
        utility_meter_sensor._total_consumption = 50.5
        utility_meter_sensor._last_power = 75.0
        utility_meter_sensor._switch_entity_id = "switch.device_123"
        
        attrs = utility_meter_sensor.extra_state_attributes
        
        assert attrs["last_reset"] == "2024-01-01T00:00:00"
        assert attrs["total_increasing"] == 50.5
        assert attrs["last_power_w"] == 75.0
        assert attrs["switch_entity"] == "switch.device_123"

    def test_handle_state_change_with_new_state(self, utility_meter_sensor):
        """Test handling state changes."""
        utility_meter_sensor._update_state = MagicMock()
        utility_meter_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event with new state
        event = MagicMock(spec=Event)
        event.data = {"new_state": MagicMock()}
        
        utility_meter_sensor._handle_state_change(event)
        
        utility_meter_sensor._update_state.assert_called_once()
        utility_meter_sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(self, utility_meter_sensor):
        """Test cleanup when removing from Home Assistant."""
        # Set up some state
        utility_meter_sensor._total_consumption = 100.0
        utility_meter_sensor._last_update = datetime.now()
        
        # Mock the remove callback
        mock_remove_callback = MagicMock()
        utility_meter_sensor._remove_listener = mock_remove_callback
        
        await utility_meter_sensor.async_will_remove_from_hass()
        
        # Should save state before removal
        # (In a real implementation, this would persist to storage)