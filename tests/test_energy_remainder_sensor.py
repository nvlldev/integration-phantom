"""Tests for the accumulated energy remainder sensor."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime
import asyncio

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers.event import EventStateChangedData

from custom_components.phantom.sensors.remainder import PhantomEnergyRemainderSensor
from custom_components.phantom.const import CONF_DEVICE_ID, DOMAIN


class TestPhantomEnergyRemainderSensor:
    """Test the PhantomEnergyRemainderSensor functionality."""

    @pytest.fixture
    def energy_remainder_sensor(self, mock_hass):
        """Create an energy remainder sensor instance."""
        return PhantomEnergyRemainderSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            upstream_entity="sensor.upstream_energy",
            devices=[
                {"name": "Device 1", CONF_DEVICE_ID: "device1_id"},
                {"name": "Device 2", CONF_DEVICE_ID: "device2_id"},
            ],
        )

    def test_init(self, energy_remainder_sensor):
        """Test sensor initialization."""
        assert energy_remainder_sensor._attr_name == "Energy Remainder"
        assert energy_remainder_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert energy_remainder_sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert energy_remainder_sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert energy_remainder_sensor._attr_icon == "mdi:lightning-bolt-outline"
        assert energy_remainder_sensor._attr_suggested_display_precision == 3
        assert energy_remainder_sensor._accumulated_remainder == 0.0
        assert energy_remainder_sensor._last_upstream_value is None
        assert energy_remainder_sensor._last_total_value is None

    def test_extra_state_attributes(self, energy_remainder_sensor):
        """Test extra state attributes."""
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        energy_remainder_sensor._accumulated_remainder = 0.05
        energy_remainder_sensor._last_upstream_value = 1.23
        energy_remainder_sensor._last_total_value = 1.18
        
        attrs = energy_remainder_sensor.extra_state_attributes
        
        assert attrs["upstream_meter"] == "sensor.upstream_meter"
        assert attrs["device_count"] == 2
        assert attrs["accumulated_remainder"] == 0.05
        assert attrs["instantaneous_remainder"] == 0.05  # 1.23 - 1.18
        assert attrs["instantaneous_remainder_percent"] == pytest.approx(4.065, rel=0.01)  # (0.05/1.23)*100
        assert attrs["last_upstream_value"] == 1.23
        assert attrs["last_total_value"] == 1.18

    def test_extra_state_attributes_no_upstream_value(self, energy_remainder_sensor):
        """Test extra state attributes when upstream value is zero."""
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = []
        energy_remainder_sensor._accumulated_remainder = 0.0
        energy_remainder_sensor._last_upstream_value = 0.0
        energy_remainder_sensor._last_total_value = 0.0
        
        attrs = energy_remainder_sensor.extra_state_attributes
        
        assert attrs["instantaneous_remainder"] == 0.0
        assert attrs["instantaneous_remainder_percent"] == 0.0

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restore_state(self, energy_remainder_sensor, mock_hass):
        """Test restoring state when added to hass."""
        # Mock last state
        mock_last_state = MagicMock(spec=State)
        mock_last_state.state = "0.123"
        mock_last_state.attributes = {
            "last_upstream_value": 2.50,
            "last_total_value": 2.377,
        }
        
        energy_remainder_sensor.async_get_last_state = AsyncMock(return_value=mock_last_state)
        energy_remainder_sensor.hass.async_create_task = MagicMock()
        
        await energy_remainder_sensor.async_added_to_hass()
        
        assert energy_remainder_sensor._accumulated_remainder == 0.123
        assert energy_remainder_sensor._attr_native_value == 0.123
        assert energy_remainder_sensor._last_upstream_value == 2.50
        assert energy_remainder_sensor._last_total_value == 2.377

    @pytest.mark.asyncio
    async def test_async_added_to_hass_no_restore(self, energy_remainder_sensor, mock_hass):
        """Test initialization when no state to restore."""
        energy_remainder_sensor.async_get_last_state = AsyncMock(return_value=None)
        energy_remainder_sensor.hass.async_create_task = MagicMock()
        
        await energy_remainder_sensor.async_added_to_hass()
        
        assert energy_remainder_sensor._accumulated_remainder == 0.0
        assert energy_remainder_sensor._attr_native_value == 0.0
        assert energy_remainder_sensor._last_upstream_value is None
        assert energy_remainder_sensor._last_total_value is None

    @pytest.mark.asyncio
    async def test_delayed_setup_with_meters(self, energy_remainder_sensor, mock_hass, mock_entity_registry):
        """Test delayed setup finding meter entities."""
        energy_remainder_sensor._setup_delayed = False
        energy_remainder_sensor.async_on_remove = MagicMock()
        energy_remainder_sensor._update_state = MagicMock()
        energy_remainder_sensor.async_write_ha_state = MagicMock()
        
        # Mock entity registry
        mock_entity_registry.entities = {
            "sensor.upstream_meter": MagicMock(
                unique_id="group_123_upstream_energy_meter",
                domain="sensor",
                platform=DOMAIN,
                config_entry_id="test_entry",
            ),
            "sensor.device1_meter": MagicMock(
                unique_id="device1_id_utility_meter",
                domain="sensor",
                platform=DOMAIN,
                config_entry_id="test_entry",
            ),
            "sensor.device2_meter": MagicMock(
                unique_id="device2_id_utility_meter",
                domain="sensor",
                platform=DOMAIN,
                config_entry_id="test_entry",
            ),
        }
        
        with patch("custom_components.phantom.sensors.remainder.er.async_get", return_value=mock_entity_registry):
            with patch("custom_components.phantom.sensors.remainder.async_track_state_change_event") as mock_track:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await energy_remainder_sensor._delayed_setup()
        
        assert energy_remainder_sensor._upstream_meter_entity == "sensor.upstream_meter"
        assert energy_remainder_sensor._utility_meter_entities == ["sensor.device1_meter", "sensor.device2_meter"]
        assert energy_remainder_sensor._setup_delayed is True
        mock_track.assert_called_once()
        energy_remainder_sensor._update_state.assert_called_once()

    def test_update_state_first_run(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test first run initialization."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "1.234"),
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.567"),
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.432"),
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Should initialize tracking values but not accumulate
        assert energy_remainder_sensor._last_upstream_value == 1.234
        assert energy_remainder_sensor._last_total_value == 0.999  # 0.567 + 0.432
        assert energy_remainder_sensor._accumulated_remainder == 0.0
        assert energy_remainder_sensor._attr_native_value == 0.0

    def test_update_state_positive_remainder_accumulation(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test accumulating positive remainder."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Set previous values
        energy_remainder_sensor._last_upstream_value = 1.0
        energy_remainder_sensor._last_total_value = 0.8
        energy_remainder_sensor._accumulated_remainder = 0.0
        
        # Mock states with increases
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "1.5"),  # +0.5
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.6"),   # Total will be 1.1
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.5"),   # So total delta = 0.3
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Should accumulate the positive remainder: (0.5 - 0.3) = 0.2
        assert energy_remainder_sensor._accumulated_remainder == pytest.approx(0.2, abs=1e-6)
        assert energy_remainder_sensor._attr_native_value == pytest.approx(0.2, abs=1e-6)
        assert energy_remainder_sensor._last_upstream_value == 1.5
        assert energy_remainder_sensor._last_total_value == 1.1

    def test_update_state_negative_remainder_not_accumulated(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test that negative remainder is not accumulated."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Set previous values
        energy_remainder_sensor._last_upstream_value = 1.0
        energy_remainder_sensor._last_total_value = 0.8
        energy_remainder_sensor._accumulated_remainder = 0.1
        
        # Mock states where total increased more than upstream
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "1.1"),  # +0.1
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.7"),   # Total will be 1.2
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.5"),   # So total delta = 0.4
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Should not accumulate negative remainder: (0.1 - 0.4) = -0.3
        assert energy_remainder_sensor._accumulated_remainder == 0.1  # Unchanged
        assert energy_remainder_sensor._attr_native_value == 0.1

    def test_update_state_meter_reset(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test handling meter reset."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Set previous values
        energy_remainder_sensor._last_upstream_value = 10.0
        energy_remainder_sensor._last_total_value = 9.5
        energy_remainder_sensor._accumulated_remainder = 0.5
        
        # Mock states with reset
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "0.1"),  # Reset
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.05"),  # Reset
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.03"),  # Reset
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Should handle reset without changing accumulated value
        assert energy_remainder_sensor._accumulated_remainder == 0.5  # Unchanged
        assert energy_remainder_sensor._attr_native_value == 0.5
        assert energy_remainder_sensor._last_upstream_value == 0.1
        assert energy_remainder_sensor._last_total_value == 0.08

    def test_update_state_sanity_check(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test sanity check prevents accumulated > instantaneous remainder."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Set accumulated remainder higher than it should be
        energy_remainder_sensor._last_upstream_value = 1.0
        energy_remainder_sensor._last_total_value = 0.8
        energy_remainder_sensor._accumulated_remainder = 1.0  # Too high!
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "2.0"),
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.9"),
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.8"),
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Should reset to instantaneous remainder: 2.0 - 1.7 = 0.3
        assert energy_remainder_sensor._accumulated_remainder == pytest.approx(0.3, abs=1e-6)
        assert energy_remainder_sensor._attr_native_value == pytest.approx(0.3, abs=1e-6)

    def test_update_state_upstream_unavailable(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test handling upstream unavailable."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        energy_remainder_sensor._accumulated_remainder = 0.25
        energy_remainder_sensor._attr_available = True
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", STATE_UNAVAILABLE),
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.5"),
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.4"),
        }.get(entity_id)
        
        with patch("custom_components.phantom.sensors.remainder.async_create_sensor_unavailable_issue"):
            energy_remainder_sensor._update_state()
        
        # Should maintain current value
        assert energy_remainder_sensor._accumulated_remainder == 0.25
        assert energy_remainder_sensor._attr_native_value == 0.25

    def test_update_state_no_devices_available(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test handling when no device meters are available."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        energy_remainder_sensor._accumulated_remainder = 0.15
        energy_remainder_sensor._attr_available = False
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "1.5"),
            "sensor.device1_meter": mock_state("sensor.device1_meter", STATE_UNKNOWN),
            "sensor.device2_meter": mock_state("sensor.device2_meter", STATE_UNAVAILABLE),
        }.get(entity_id)
        
        with patch("custom_components.phantom.sensors.remainder.async_create_sensor_unavailable_issue"):
            energy_remainder_sensor._update_state()
        
        # Should maintain accumulated value
        assert energy_remainder_sensor._accumulated_remainder == 0.15
        assert energy_remainder_sensor._attr_native_value == 0.15

    def test_handle_state_change(self, energy_remainder_sensor):
        """Test state change event handler."""
        energy_remainder_sensor._update_state = MagicMock()
        energy_remainder_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event
        mock_event = MagicMock(spec=Event)
        mock_new_state = MagicMock()
        mock_event.data = {"new_state": mock_new_state}
        
        energy_remainder_sensor._handle_state_change(mock_event)
        
        energy_remainder_sensor._update_state.assert_called_once()
        energy_remainder_sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_reset(self, energy_remainder_sensor):
        """Test resetting the sensor."""
        # Set some values
        energy_remainder_sensor._accumulated_remainder = 0.123
        energy_remainder_sensor._last_upstream_value = 2.5
        energy_remainder_sensor._last_total_value = 2.377
        energy_remainder_sensor._attr_native_value = 0.123
        
        energy_remainder_sensor._update_state = MagicMock()
        energy_remainder_sensor.async_write_ha_state = MagicMock()
        
        await energy_remainder_sensor.async_reset()
        
        # Should reset all values
        assert energy_remainder_sensor._accumulated_remainder == 0.0
        assert energy_remainder_sensor._attr_native_value == 0.0
        assert energy_remainder_sensor._last_upstream_value is None
        assert energy_remainder_sensor._last_total_value is None
        energy_remainder_sensor._update_state.assert_called_once()
        energy_remainder_sensor.async_write_ha_state.assert_called_once()

    def test_precision_handling(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test that full precision is maintained in calculations."""
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Set previous values with high precision
        energy_remainder_sensor._last_upstream_value = 1.123456789
        energy_remainder_sensor._last_total_value = 1.076543210
        energy_remainder_sensor._accumulated_remainder = 0.0
        
        # Mock states with small increases
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "1.123456999"),  # +0.00000021
            "sensor.device1_meter": mock_state("sensor.device1_meter", "0.538271605"),
            "sensor.device2_meter": mock_state("sensor.device2_meter", "0.538271705"),  # Total: 1.07654331 (+0.0000001)
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Should accumulate the tiny positive remainder with full precision
        expected_remainder = 0.00000021 - 0.0000001  # 0.00000011
        assert energy_remainder_sensor._accumulated_remainder == pytest.approx(expected_remainder, abs=1e-9)
        assert energy_remainder_sensor._last_upstream_value == 1.123456999
        assert energy_remainder_sensor._last_total_value == pytest.approx(1.07654331, abs=1e-9)