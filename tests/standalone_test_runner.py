#!/usr/bin/env python3
"""Standalone test runner that runs tests without pytest to bypass import issues."""
import sys
import os
import traceback
from unittest.mock import MagicMock, Mock, AsyncMock, patch
from datetime import datetime, time
import asyncio

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set up all necessary mocks before any imports
print("Setting up mock environment...")

# Mock all problematic modules
mock_modules = [
    'homeassistant.components',
    'homeassistant.components.http',
    'homeassistant.components.http.auth',
    'homeassistant.components.http.static',
    'homeassistant.components.websocket_api',
    'homeassistant.components.websocket_api.http',
    'homeassistant.components.persistent_notification',
    'homeassistant.components.frontend',
    'homeassistant.components.onboarding',
    'homeassistant.components.onboarding.views',
    'homeassistant.components.auth',
    'homeassistant.components.auth.indieauth',
    'homeassistant.components.sensor',
    'custom_components.phantom.panel',
    'custom_components.phantom.api',
    'custom_components.phantom.coordinator',
]

for module in mock_modules:
    sys.modules[module] = MagicMock()

# Set up sensor module properly
sensor_module = MagicMock()
sensor_module.SensorEntity = type('SensorEntity', (object,), {
    '_attr_should_poll': False,
    '_attr_has_entity_name': True,
})
sensor_module.SensorStateClass = Mock(
    MEASUREMENT='measurement',
    TOTAL_INCREASING='total_increasing'
)
sensor_module.SensorDeviceClass = Mock(
    POWER='power',
    ENERGY='energy'
)
sys.modules['homeassistant.components.sensor'] = sensor_module

# Import HA modules and set up constants
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfPower, UnitOfEnergy
from homeassistant.core import HomeAssistant, State, Event
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er

# Get sensor classes from our mock
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass

# Mock repairs module
sys.modules['custom_components.phantom.repairs'] = MagicMock()
repairs_mock = sys.modules['custom_components.phantom.repairs']
repairs_mock.async_create_sensor_unavailable_issue = AsyncMock()
repairs_mock.async_delete_sensor_unavailable_issue = AsyncMock()
repairs_mock.async_create_upstream_unavailable_issue = AsyncMock()
repairs_mock.async_delete_upstream_unavailable_issue = AsyncMock()

# Mock migration helpers
sys.modules['custom_components.phantom.migrations'] = MagicMock()
migrations_mock = sys.modules['custom_components.phantom.migrations']
migrations_mock.get_migrated_state = MagicMock(return_value=None)

# Mock utils module
sys.modules['custom_components.phantom.utils'] = MagicMock()
utils_mock = sys.modules['custom_components.phantom.utils']
utils_mock.sanitize_name = MagicMock(side_effect=lambda x: x.lower().replace(" ", "_"))

# Import our modules
from custom_components.phantom.const import DOMAIN, CONF_DEVICE_ID
from custom_components.phantom.tariff import TariffManager

# Mock ExternalTariffManager for cost tests
sys.modules['custom_components.phantom.tariff'].ExternalTariffManager = MagicMock

# Import migration function for upstream sensor
from custom_components.phantom.migrations import get_migrated_state

# Import all sensor classes
from custom_components.phantom.sensors.base import PhantomBaseSensor, PhantomDeviceSensor
from custom_components.phantom.sensors.remainder import PhantomPowerRemainderSensor, PhantomEnergyRemainderSensor
from custom_components.phantom.sensors.remainder_cost import PhantomCostRemainderSensor
from custom_components.phantom.sensors.energy import PhantomEnergySensor, PhantomUtilityMeterSensor
from custom_components.phantom.sensors.cost import (
    PhantomGroupTotalCostSensor, PhantomDeviceHourlyCostSensor,
    PhantomGroupHourlyCostSensor, PhantomTouRateSensor, PhantomDeviceTotalCostSensor
)
from custom_components.phantom.sensors.power import PhantomPowerSensor, PhantomIndividualPowerSensor
from custom_components.phantom.sensors.upstream import PhantomUpstreamPowerSensor, PhantomUpstreamEnergyMeterSensor


class TestRunner:
    """Run tests for sensor classes."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
        
    def create_mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        hass.data = {}
        hass.bus = MagicMock()
        hass.async_create_task = MagicMock()
        hass.config = MagicMock()
        hass.config.units = MagicMock()
        return hass
        
    def create_mock_state(self, entity_id, state_value, attributes=None):
        """Create a mock state."""
        state = MagicMock(spec=State)
        state.entity_id = entity_id
        state.state = state_value
        state.attributes = attributes or {}
        state.last_changed = datetime.now()
        state.last_updated = datetime.now()
        return state
        
    def create_mock_tariff_manager(self):
        """Create a mock tariff manager."""
        manager = MagicMock(spec=TariffManager)
        manager.currency = "USD"
        manager.currency_symbol = "$"
        manager.get_current_rate = MagicMock(return_value=0.15)
        manager.get_current_period_info = MagicMock(return_value=None)
        # Mock calculate_cost_per_hour to return power_watts / 1000 * rate
        manager.calculate_cost_per_hour = MagicMock(side_effect=lambda power_watts: power_watts / 1000 * 0.15)
        return manager
        
    def run_test(self, test_name, test_func):
        """Run a single test."""
        try:
            print(f"  Running {test_name}...", end=" ")
            result = test_func()
            if asyncio.iscoroutine(result):
                asyncio.run(result)
            print("✅ PASSED")
            self.passed += 1
            return True
        except Exception as e:
            print(f"❌ FAILED: {str(e)}")
            if "--verbose" in sys.argv:
                traceback.print_exc()
            self.failed += 1
            return False
            
    def test_base_sensors(self):
        """Test base sensor functionality."""
        print("\n=== Testing Base Sensors ===")
        
        # Test PhantomBaseSensor initialization
        self.run_test("PhantomBaseSensor initialization", lambda: self._test_base_sensor_init())
        
        # Test PhantomDeviceSensor initialization
        self.run_test("PhantomDeviceSensor initialization", lambda: self._test_device_sensor_init())
        
    def _test_base_sensor_init(self):
        """Test base sensor initialization."""
        sensor = PhantomBaseSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            sensor_type="test_sensor"
        )
        assert sensor._group_name == "Test Group"
        assert sensor._group_id == "group_123"
        assert sensor._attr_should_poll is False
        assert sensor._attr_unique_id == "group_123_test_sensor"
        
    def _test_device_sensor_init(self):
        """Test device sensor initialization."""
        sensor = PhantomDeviceSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            sensor_type="test_sensor"
        )
        assert sensor._device_name == "Test Device"
        assert sensor._device_id == "device_123"
        assert sensor._attr_unique_id == "device_123_test_sensor"
        
    def test_remainder_sensors(self):
        """Test remainder sensor functionality."""
        print("\n=== Testing Remainder Sensors ===")
        
        # Test power remainder sensor
        self.run_test("PhantomPowerRemainderSensor calculation", lambda: self._test_power_remainder_calc())
        
        # Test energy remainder sensor
        self.run_test("PhantomEnergyRemainderSensor initialization", lambda: self._test_energy_remainder_init())
        
        # Test cost remainder sensor
        self.run_test("PhantomCostRemainderSensor negative values", lambda: self._test_cost_remainder_negative())
        
    def _test_power_remainder_calc(self):
        """Test power remainder calculation."""
        sensor = PhantomPowerRemainderSensor(
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_entity="sensor.upstream",
            power_entities=["sensor.device1", "sensor.device2"]
        )
        hass = self.create_mock_hass()
        sensor.hass = hass
        
        # Mock states
        hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream": self.create_mock_state("sensor.upstream", "100"),
            "sensor.device1": self.create_mock_state("sensor.device1", "30"),
            "sensor.device2": self.create_mock_state("sensor.device2", "25"),
        }.get(entity_id)
        
        sensor._update_state()
        assert sensor._attr_native_value == 45  # 100 - 30 - 25
        
    def _test_energy_remainder_init(self):
        """Test energy remainder initialization."""
        hass = self.create_mock_hass()
        sensor = PhantomEnergyRemainderSensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_entity="sensor.upstream",
            devices=[{CONF_DEVICE_ID: "device1"}]
        )
        assert sensor._attr_name == "Energy Remainder"
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        
    def _test_cost_remainder_negative(self):
        """Test cost remainder can be negative."""
        hass = self.create_mock_hass()
        sensor = PhantomCostRemainderSensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_cost_entity="sensor.upstream",
            device_cost_entities=["sensor.device1"],
            currency="USD",
            currency_symbol="$"
        )
        
        # Mock states where devices cost more than upstream
        hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream": self.create_mock_state("sensor.upstream", "5.00"),
            "sensor.device1": self.create_mock_state("sensor.device1", "6.00"),
        }.get(entity_id)
        
        sensor._update_state()
        assert sensor._attr_native_value == -1.00  # Can be negative
        
    def test_power_sensors(self):
        """Test power sensor functionality."""
        print("\n=== Testing Power Sensors ===")
        
        self.run_test("PhantomPowerSensor total calculation", lambda: self._test_power_sensor_total())
        self.run_test("PhantomIndividualPowerSensor switch tracking", lambda: self._test_individual_power())
        
    def _test_power_sensor_total(self):
        """Test power sensor total calculation."""
        hass = self.create_mock_hass()
        sensor = PhantomPowerSensor(
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            power_entities=["sensor.device1_power", "sensor.device2_power"]
        )
        sensor.hass = hass
        
        # Mock power states
        hass.states.get.side_effect = lambda entity_id: {
            "sensor.device1_power": self.create_mock_state("sensor.device1_power", "150"),
            "sensor.device2_power": self.create_mock_state("sensor.device2_power", "200"),
        }.get(entity_id)
        
        sensor._update_state()
        assert sensor._attr_native_value == 350  # 150 + 200
        
    def _test_individual_power(self):
        """Test individual power sensor."""
        sensor = PhantomIndividualPowerSensor(
            config_entry_id="test",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            power_entity="switch.device_123"
        )
        assert sensor._attr_unique_id == "device_123_power"
        assert sensor._attr_device_class == SensorDeviceClass.POWER
        
    def test_energy_sensors(self):
        """Test energy sensor functionality."""
        print("\n=== Testing Energy Sensors ===")
        
        self.run_test("PhantomEnergySensor initialization", lambda: self._test_energy_sensor_init())
        self.run_test("PhantomUtilityMeterSensor initialization", lambda: self._test_utility_meter_init())
        
    def _test_energy_sensor_init(self):
        """Test energy sensor initialization."""
        hass = self.create_mock_hass()
        sensor = PhantomEnergySensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            devices=[]
        )
        assert sensor._attr_name == "Energy Total"
        assert sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        
    def _test_utility_meter_init(self):
        """Test utility meter initialization."""
        hass = self.create_mock_hass()
        sensor = PhantomUtilityMeterSensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            energy_entity="sensor.device_energy"
        )
        assert sensor._attr_unique_id == "device_123_utility_meter"
        assert sensor._attr_device_class == SensorDeviceClass.ENERGY
        
    def test_cost_sensors(self):
        """Test cost sensor functionality."""
        print("\n=== Testing Cost Sensors ===")
        
        self.run_test("PhantomGroupTotalCostSensor initialization", lambda: self._test_group_cost_init())
        self.run_test("PhantomDeviceHourlyCostSensor calculation", lambda: self._test_hourly_cost_calc())
        self.run_test("PhantomTouRateSensor initialization", lambda: self._test_tou_rate_init())
        
    def _test_group_cost_init(self):
        """Test group cost sensor initialization."""
        hass = self.create_mock_hass()
        tariff_manager = self.create_mock_tariff_manager()
        sensor = PhantomGroupTotalCostSensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            devices=[],
            tariff_manager=tariff_manager
        )
        assert sensor._attr_name == "Total Cost"
        assert sensor._attr_native_unit_of_measurement == "USD"
        
    def _test_hourly_cost_calc(self):
        """Test hourly cost calculation."""
        tariff_manager = self.create_mock_tariff_manager()
        hass = self.create_mock_hass()
        sensor = PhantomDeviceHourlyCostSensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test Group",
            device_name="Test Device",
            device_id="device_123",
            power_entity="sensor.device_power",
            tariff_manager=tariff_manager
        )
        
        # Mock 500W power
        hass.states.get.return_value = self.create_mock_state("sensor.device_power", "500")
        
        sensor._update_state()
        # 500W * 0.15$/kWh = 0.075$/h
        # Check if the value is set (not MagicMock)
        assert hasattr(sensor, '_attr_native_value')
        assert sensor._attr_native_value is not None
        assert sensor._attr_native_value == 0.075
        
    def _test_tou_rate_init(self):
        """Test TOU rate sensor initialization."""
        tariff_manager = self.create_mock_tariff_manager()
        sensor = PhantomTouRateSensor(
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            tariff_manager=tariff_manager
        )
        assert sensor._attr_name == "Current Electricity Rate"
        assert sensor._attr_unique_id == "group_123_current_rate"
        
    def test_upstream_sensors(self):
        """Test upstream sensor functionality."""
        print("\n=== Testing Upstream Sensors ===")
        
        self.run_test("PhantomUpstreamPowerSensor initialization", lambda: self._test_upstream_power_init())
        self.run_test("PhantomUpstreamEnergyMeterSensor initialization", lambda: self._test_upstream_energy_init())
        
    def _test_upstream_power_init(self):
        """Test upstream power sensor initialization."""
        sensor = PhantomUpstreamPowerSensor(
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_entity="sensor.meter"
        )
        assert sensor._attr_name == "Upstream Power"
        assert sensor._attr_unique_id == "group_123_upstream_power"
        
    def _test_upstream_energy_init(self):
        """Test upstream energy sensor initialization."""
        hass = self.create_mock_hass()
        sensor = PhantomUpstreamEnergyMeterSensor(
            hass=hass,
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_entity="sensor.meter"
        )
        assert sensor._attr_name == "Upstream Energy Meter"
        assert isinstance(sensor, RestoreEntity)
        
    def test_additional_coverage(self):
        """Test additional scenarios for better coverage."""
        print("\n=== Additional Coverage Tests ===")
        
        self.run_test("Device info generation", lambda: self._test_device_info())
        self.run_test("State restoration handling", lambda: self._test_state_restoration())
        self.run_test("Event handling validation", lambda: self._test_event_handling())
        
    def _test_device_info(self):
        """Test device info generation."""
        sensor = PhantomBaseSensor(
            config_entry_id="test",
            group_name="Test Group",
            group_id="group_123",
            sensor_type="test"
        )
        device_info = sensor.device_info
        assert device_info["name"] == "Phantom Test Group"
        assert device_info["manufacturer"] == "Phantom"
        assert (DOMAIN, "test_test_group") in device_info["identifiers"]
        
    async def _test_state_restoration(self):
        """Test state restoration with RestoreEntity."""
        hass = self.create_mock_hass()
        sensor = PhantomPowerRemainderSensor(
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_entity="sensor.upstream",
            power_entities=[]
        )
        sensor.hass = hass
        
        # Mock last state
        mock_last_state = MagicMock()
        mock_last_state.state = "123.45"
        sensor.async_get_last_state = AsyncMock(return_value=mock_last_state)
        
        # Mock event tracking
        with patch("custom_components.phantom.sensors.remainder.async_track_state_change_event"):
            await sensor.async_added_to_hass()
        
        assert sensor._attr_native_value == 123.45
        assert sensor._attr_available is True
        
    def _test_event_handling(self):
        """Test event handling."""
        sensor = PhantomPowerRemainderSensor(
            config_entry_id="test",
            group_name="Test",
            group_id="group_123",
            upstream_entity="sensor.upstream",
            power_entities=[]
        )
        
        # Mock update methods
        sensor._update_state = MagicMock()
        sensor.async_write_ha_state = MagicMock()
        
        # Create event with new state
        event = MagicMock(spec=Event)
        event.data = {"new_state": MagicMock()}
        
        sensor._handle_state_change(event)
        
        sensor._update_state.assert_called_once()
        sensor.async_write_ha_state.assert_called_once()

    def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("Running Phantom Integration Tests")
        print("=" * 60)
        
        self.test_base_sensors()
        self.test_remainder_sensors()
        self.test_power_sensors()
        self.test_energy_sensors()
        self.test_cost_sensors()
        self.test_upstream_sensors()
        self.test_additional_coverage()
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Total: {self.passed + self.failed}")
        
        if self.failed == 0:
            print("\n🎉 All tests passed!")
            return 0
        else:
            print(f"\n❌ {self.failed} test(s) failed")
            return 1


if __name__ == "__main__":
    runner = TestRunner()
    sys.exit(runner.run_all_tests())