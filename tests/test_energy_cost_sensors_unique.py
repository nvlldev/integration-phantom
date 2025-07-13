"""Tests for unique energy and cost sensor functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import asyncio

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers import entity_registry as er

from custom_components.phantom.sensors.energy import PhantomEnergySensor
from custom_components.phantom.sensors.cost import PhantomGroupTotalCostSensor
from custom_components.phantom.tariff import TariffManager
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID


class TestPhantomEnergySensor:
    """Test the PhantomEnergySensor unique functionality."""

    @pytest.fixture
    def energy_sensor(self, mock_hass):
        """Create an energy sensor instance."""
        sensor = PhantomEnergySensor(
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

    def test_init(self, energy_sensor):
        """Test sensor initialization."""
        assert energy_sensor._attr_name == "Energy Total"
        assert energy_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert energy_sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        assert energy_sensor._attr_device_class == SensorDeviceClass.ENERGY
        assert energy_sensor._attr_icon == "mdi:lightning-bolt"
        assert energy_sensor._attr_suggested_display_precision == 3

    @pytest.mark.asyncio
    async def test_delayed_setup_utility_meter_discovery(self, energy_sensor, mock_hass, mock_entity_registry):
        """Test delayed setup discovers utility meter entities."""
        energy_sensor.async_on_remove = MagicMock()
        energy_sensor._update_state = MagicMock()
        energy_sensor.async_write_ha_state = MagicMock()
        
        # Mock entity registry
        mock_entity_registry.entities = {
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
        
        with patch("custom_components.phantom.sensors.energy.er.async_get", return_value=mock_entity_registry):
            with patch("custom_components.phantom.sensors.energy.async_track_state_change_event") as mock_track:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await energy_sensor._delayed_setup()
        
        # Should find utility meter entities
        assert energy_sensor._utility_meter_entities == ["sensor.device1_meter", "sensor.device2_meter"]
        
        # Should set up tracking
        mock_track.assert_called_once()
        
        # Should mark setup as complete
        assert energy_sensor._setup_delayed is True

    def test_update_state_energy_total_calculation(self, energy_sensor, mock_hass, mock_state):
        """Test energy total calculation with floating point precision."""
        energy_sensor.hass = mock_hass
        energy_sensor._setup_delayed = True
        energy_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        energy_sensor._attr_native_value = 0.0
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_meter": mock_state("sensor.device1_meter", "50.123"),
            "sensor.device2_meter": mock_state("sensor.device2_meter", "75.456"),
        }.get(entity_id)
        
        energy_sensor._update_state()
        
        # Should calculate total: 50.123 + 75.456 = 125.579
        assert abs(energy_sensor._attr_native_value - 125.579) < 0.001

    def test_update_state_with_repair_issues(self, energy_sensor, mock_hass, mock_state):
        """Test state update creates/deletes repair issues when all unavailable."""
        energy_sensor.hass = mock_hass
        energy_sensor._setup_delayed = True
        energy_sensor._utility_meter_entities = ["sensor.device1_meter", "sensor.device2_meter"]
        energy_sensor._attr_native_value = 100.0
        
        # Mock states all unavailable
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_meter": mock_state("sensor.device1_meter", STATE_UNAVAILABLE),
            "sensor.device2_meter": mock_state("sensor.device2_meter", STATE_UNKNOWN),
        }.get(entity_id)
        
        # Mock the async repair functions
        with patch("custom_components.phantom.sensors.energy.async_create_sensor_unavailable_issue") as mock_create:
            with patch("custom_components.phantom.sensors.energy.async_delete_sensor_unavailable_issue"):
                energy_sensor._update_state()
                
                # Should create repair issue
                mock_create.assert_called_once()
                assert energy_sensor._issue_created is True
        
        # Should return 0
        assert energy_sensor._attr_native_value == 0.0


class TestPhantomGroupTotalCostSensor:
    """Test the PhantomGroupTotalCostSensor unique functionality."""

    @pytest.fixture
    def mock_tariff_manager(self):
        """Create a mock tariff manager."""
        tariff_manager = MagicMock(spec=TariffManager)
        tariff_manager.currency = "USD"
        tariff_manager.currency_symbol = "$"
        return tariff_manager

    @pytest.fixture
    def group_cost_sensor(self, mock_hass, mock_tariff_manager):
        """Create a group total cost sensor instance."""
        sensor = PhantomGroupTotalCostSensor(
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

    def test_init(self, group_cost_sensor, mock_tariff_manager):
        """Test sensor initialization."""
        assert group_cost_sensor._attr_name == "Total Cost"
        assert group_cost_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert group_cost_sensor._attr_native_unit_of_measurement == "USD"
        assert group_cost_sensor._attr_icon == "mdi:cash-multiple"
        assert group_cost_sensor._attr_suggested_display_precision == 2

    def test_extra_state_attributes(self, group_cost_sensor):
        """Test extra state attributes."""
        group_cost_sensor._device_cost_entities = ["sensor.device1_cost", "sensor.device2_cost"]
        attrs = group_cost_sensor.extra_state_attributes
        assert attrs["currency_symbol"] == "$"
        assert attrs["device_count"] == 2

    @pytest.mark.asyncio
    async def test_delayed_setup_cost_entity_discovery(self, group_cost_sensor, mock_hass, mock_entity_registry):
        """Test delayed setup discovers device cost entities."""
        group_cost_sensor.async_on_remove = MagicMock()
        group_cost_sensor._update_state = MagicMock()
        group_cost_sensor.async_write_ha_state = MagicMock()
        
        # Mock entity registry
        mock_entity_registry.entities = {
            "sensor.device1_total_cost": MagicMock(
                unique_id="device1_id_total_cost",
                domain="sensor",
                platform=DOMAIN,
            ),
            "sensor.device2_total_cost": MagicMock(
                unique_id="device2_id_total_cost",
                domain="sensor",
                platform=DOMAIN,
            ),
        }
        
        with patch("custom_components.phantom.sensors.cost.er.async_get", return_value=mock_entity_registry):
            with patch("custom_components.phantom.sensors.cost.async_track_state_change_event") as mock_track:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await group_cost_sensor._delayed_setup()
        
        # Should find device cost entities
        assert group_cost_sensor._device_cost_entities == ["sensor.device1_total_cost", "sensor.device2_total_cost"]
        
        # Should set up tracking
        mock_track.assert_called_once()
        
        # Should mark setup as complete
        assert group_cost_sensor._setup_delayed is True

    def test_update_state_cost_aggregation(self, group_cost_sensor, mock_hass, mock_state):
        """Test cost aggregation from multiple devices."""
        group_cost_sensor.hass = mock_hass
        group_cost_sensor._setup_delayed = True
        group_cost_sensor._device_cost_entities = ["sensor.device1_cost", "sensor.device2_cost", "sensor.device3_cost"]
        
        # Mock states with various cost values
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_cost": mock_state("sensor.device1_cost", "25.50"),
            "sensor.device2_cost": mock_state("sensor.device2_cost", "30.75"),
            "sensor.device3_cost": mock_state("sensor.device3_cost", "15.25"),
        }.get(entity_id)
        
        group_cost_sensor._update_state()
        
        # Should calculate total: 25.50 + 30.75 + 15.25 = 71.50
        assert group_cost_sensor._attr_native_value == 71.50

    def test_update_state_mixed_availability(self, group_cost_sensor, mock_hass, mock_state):
        """Test update with some cost sensors unavailable."""
        group_cost_sensor.hass = mock_hass
        group_cost_sensor._setup_delayed = True
        group_cost_sensor._device_cost_entities = ["sensor.device1_cost", "sensor.device2_cost", "sensor.device3_cost"]
        
        # Mock states with mixed availability
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_cost": mock_state("sensor.device1_cost", "25.50"),
            "sensor.device2_cost": mock_state("sensor.device2_cost", STATE_UNAVAILABLE),
            "sensor.device3_cost": mock_state("sensor.device3_cost", "15.25"),
        }.get(entity_id)
        
        group_cost_sensor._update_state()
        
        # Should only sum available: 25.50 + 15.25 = 40.75
        assert group_cost_sensor._attr_native_value == 40.75