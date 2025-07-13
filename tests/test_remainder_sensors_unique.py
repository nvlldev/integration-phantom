"""Tests for unique remainder sensor functionality."""
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
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers import entity_registry as er

from custom_components.phantom.sensors.remainder import (
    PhantomPowerRemainderSensor,
    PhantomEnergyRemainderSensor,
)
from custom_components.phantom.sensors.remainder_cost import PhantomCostRemainderSensor
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestPhantomPowerRemainderSensor:
    """Test the PhantomPowerRemainderSensor unique functionality."""

    @pytest.fixture
    def power_remainder_sensor(self):
        """Create a power remainder sensor instance."""
        return PhantomPowerRemainderSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            upstream_entity="sensor.upstream_power",
            power_entities=["sensor.device1_power", "sensor.device2_power"],
        )

    def test_init(self, power_remainder_sensor):
        """Test sensor initialization."""
        assert power_remainder_sensor._attr_name == "Power Remainder"
        assert power_remainder_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert power_remainder_sensor._attr_native_unit_of_measurement == UnitOfPower.WATT
        assert power_remainder_sensor._attr_device_class == SensorDeviceClass.POWER
        assert power_remainder_sensor._attr_icon == "mdi:flash-outline"

    def test_update_state_normal(self, power_remainder_sensor, mock_hass, mock_state):
        """Test normal state update with power calculation."""
        power_remainder_sensor.hass = mock_hass
        power_remainder_sensor._attr_available = False
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_power": mock_state("sensor.upstream_power", "100"),
            "sensor.device1_power": mock_state("sensor.device1_power", "30"),
            "sensor.device2_power": mock_state("sensor.device2_power", "25"),
        }.get(entity_id)
        
        power_remainder_sensor._update_state()
        
        # Should calculate remainder: 100 - (30 + 25) = 45
        assert power_remainder_sensor._attr_native_value == 45
        assert power_remainder_sensor._attr_available is True

    def test_update_state_upstream_unavailable_keep_previous(self, power_remainder_sensor, mock_hass, mock_state):
        """Test that power remainder keeps previous value when upstream unavailable."""
        power_remainder_sensor.hass = mock_hass
        power_remainder_sensor._attr_available = True
        power_remainder_sensor._attr_native_value = 45.0
        
        # Mock states with upstream unavailable
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_power": mock_state("sensor.upstream_power", STATE_UNAVAILABLE),
            "sensor.device1_power": mock_state("sensor.device1_power", "30"),
            "sensor.device2_power": mock_state("sensor.device2_power", "25"),
        }.get(entity_id)
        
        # Mock the async repair functions
        with patch("custom_components.phantom.sensors.remainder.async_create_upstream_unavailable_issue"):
            with patch("custom_components.phantom.sensors.remainder.async_delete_upstream_unavailable_issue"):
                power_remainder_sensor._update_state()
        
        # Should keep previous value
        assert power_remainder_sensor._attr_native_value == 45.0

    def test_update_state_some_devices_unavailable(self, power_remainder_sensor, mock_hass, mock_state):
        """Test state update when some devices are unavailable."""
        power_remainder_sensor.hass = mock_hass
        power_remainder_sensor._attr_available = False
        
        # Mock states with one device unavailable
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_power": mock_state("sensor.upstream_power", "100"),
            "sensor.device1_power": mock_state("sensor.device1_power", "30"),
            "sensor.device2_power": mock_state("sensor.device2_power", STATE_UNAVAILABLE),
        }.get(entity_id)
        
        power_remainder_sensor._update_state()
        
        # Should calculate with available devices: 100 - 30 = 70
        assert power_remainder_sensor._attr_native_value == 70
        assert power_remainder_sensor._attr_available is True


class TestPhantomEnergyRemainderSensor:
    """Test the PhantomEnergyRemainderSensor unique functionality."""

    @pytest.fixture
    def energy_remainder_sensor(self, mock_hass):
        """Create an energy remainder sensor instance."""
        sensor = PhantomEnergyRemainderSensor(
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
        sensor.hass = mock_hass
        return sensor

    def test_init(self, energy_remainder_sensor):
        """Test sensor initialization."""
        assert energy_remainder_sensor._attr_name == "Energy Remainder"
        assert energy_remainder_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert energy_remainder_sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert energy_remainder_sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert energy_remainder_sensor._attr_icon == "mdi:lightning-bolt-outline"

    @pytest.mark.asyncio
    async def test_delayed_setup_with_meter_discovery(self, energy_remainder_sensor, mock_hass, mock_entity_registry):
        """Test delayed setup with utility meter discovery."""
        energy_remainder_sensor.async_on_remove = MagicMock()
        energy_remainder_sensor._update_state = MagicMock()
        energy_remainder_sensor.async_write_ha_state = MagicMock()
        
        # Mock entity registry
        mock_entity_registry.entities = {
            "sensor.upstream_meter": MagicMock(
                unique_id="group_123_upstream_energy_meter",
                domain="sensor",
                platform=DOMAIN,
            ),
            "sensor.device1_meter": MagicMock(
                unique_id="device1_id_utility_meter",
                domain="sensor",
                platform=DOMAIN,
            ),
            "sensor.device2_meter": MagicMock(
                unique_id="device2_id_utility_meter",
                domain="sensor",
                platform=DOMAIN,
            ),
        }
        
        with patch("custom_components.phantom.sensors.remainder.er.async_get", return_value=mock_entity_registry):
            with patch("custom_components.phantom.sensors.remainder.async_track_state_change_event") as mock_track:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await energy_remainder_sensor._delayed_setup()
        
        # Should find meter entities
        assert energy_remainder_sensor._upstream_meter_entity == "sensor.upstream_meter"
        assert energy_remainder_sensor._utility_meter_entities == ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Should set up tracking
        mock_track.assert_called_once()
        
        # Should mark setup as complete
        assert energy_remainder_sensor._setup_delayed is True

    def test_update_state_negative_remainder_prevention(self, energy_remainder_sensor, mock_hass, mock_state):
        """Test that energy remainder never goes negative."""
        energy_remainder_sensor.hass = mock_hass
        energy_remainder_sensor._setup_delayed = True
        energy_remainder_sensor._upstream_meter_entity = "sensor.upstream_meter"
        energy_remainder_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        energy_remainder_sensor._attr_available = False
        
        # Mock states where total exceeds upstream
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_meter": mock_state("sensor.upstream_meter", "50"),
            "sensor.device1_meter": mock_state("sensor.device1_meter", "30"),
            "sensor.device2_meter": mock_state("sensor.device2_meter", "25"),
        }.get(entity_id)
        
        energy_remainder_sensor._update_state()
        
        # Energy remainder should not go negative
        assert energy_remainder_sensor._attr_native_value == 0
        assert energy_remainder_sensor._attr_available is True


class TestPhantomCostRemainderSensor:
    """Test the PhantomCostRemainderSensor unique functionality."""

    @pytest.fixture
    def cost_remainder_sensor(self, mock_hass):
        """Create a cost remainder sensor instance."""
        return PhantomCostRemainderSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            upstream_cost_entity="sensor.upstream_cost",
            device_cost_entities=["sensor.device1_cost", "sensor.device2_cost"],
            currency="USD",
            currency_symbol="$",
        )

    def test_init(self, cost_remainder_sensor):
        """Test sensor initialization."""
        assert cost_remainder_sensor._attr_name == "Cost Remainder"
        assert cost_remainder_sensor._attr_state_class == SensorStateClass.MEASUREMENT
        assert cost_remainder_sensor._attr_native_unit_of_measurement == "USD"
        assert cost_remainder_sensor._attr_icon == "mdi:cash-minus"

    def test_extra_state_attributes(self, cost_remainder_sensor):
        """Test extra state attributes."""
        cost_remainder_sensor._device_cost_entities = ["sensor.device1_cost", "sensor.device2_cost"]
        attrs = cost_remainder_sensor.extra_state_attributes
        assert attrs["currency_symbol"] == "$"
        assert attrs["device_count"] == 2
        assert attrs["upstream_cost_entity"] == "sensor.upstream_cost"

    def test_update_state_negative_remainder(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test that cost remainder can be negative (overage)."""
        cost_remainder_sensor.hass = mock_hass
        cost_remainder_sensor._attr_available = False
        
        # Mock states where total exceeds upstream
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "5.00"),
            "sensor.device1_cost": mock_state("sensor.device1_cost", "3.25"),
            "sensor.device2_cost": mock_state("sensor.device2_cost", "2.75"),
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Cost remainder can be negative (overage)
        assert cost_remainder_sensor._attr_native_value == -1.00
        assert cost_remainder_sensor._attr_available is True

    def test_update_state_no_upstream(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test state update when there's no upstream entity."""
        cost_remainder_sensor._upstream_cost_entity = None
        cost_remainder_sensor._attr_available = False
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_cost": mock_state("sensor.device1_cost", "3.25"),
            "sensor.device2_cost": mock_state("sensor.device2_cost", "2.75"),
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should return negative total (no upstream to subtract from)
        assert cost_remainder_sensor._attr_native_value == -6.00
        assert cost_remainder_sensor._attr_available is True