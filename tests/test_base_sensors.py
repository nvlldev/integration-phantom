"""Tests for base sensor functionality."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.phantom.sensors.base import (
    PhantomBaseSensor,
    PhantomDeviceSensor,
)
from custom_components.phantom.const import DOMAIN


class TestPhantomBaseSensor:
    """Test the PhantomBaseSensor base class."""

    @pytest.fixture
    def base_sensor(self):
        """Create a base sensor instance."""
        return PhantomBaseSensor(
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
        )

    def test_init(self, base_sensor):
        """Test base sensor initialization."""
        assert base_sensor._config_entry_id == "test_entry"
        assert base_sensor._group_name == "Test Group"
        assert base_sensor._group_id == "group_123"
        assert base_sensor._attr_should_poll is False
        assert base_sensor._attr_has_entity_name is True

    def test_device_info(self, base_sensor):
        """Test device info generation."""
        device_info = base_sensor.device_info
        
        assert isinstance(device_info, DeviceInfo)
        assert device_info["identifiers"] == {(DOMAIN, "group_123")}
        assert device_info["name"] == "Test Group"
        assert device_info["manufacturer"] == "Emporia"
        assert device_info["model"] == "Smart Plug Group"
        assert device_info["configuration_url"] is None

    def test_unique_id_not_implemented(self, base_sensor):
        """Test that unique_id must be implemented by subclasses."""
        with pytest.raises(NotImplementedError):
            _ = base_sensor.unique_id

    def test_available_default(self, base_sensor):
        """Test default availability."""
        # Should use Home Assistant's default behavior
        assert hasattr(base_sensor, '_attr_available') is False

    def test_entity_attributes(self, base_sensor):
        """Test entity attributes."""
        # Test that sensor is a SensorEntity
        assert isinstance(base_sensor, SensorEntity)
        
        # Test polling is disabled
        assert base_sensor.should_poll is False
        
        # Test has entity name
        assert base_sensor.has_entity_name is True


class TestPhantomDeviceSensor:
    """Test the PhantomDeviceSensor base class."""

    @pytest.fixture
    def device_sensor(self):
        """Create a device sensor instance."""
        return PhantomDeviceSensor(
            config_entry_id="test_entry",
            device_name="Test Device",
            device_id="device_123",
        )

    def test_init(self, device_sensor):
        """Test device sensor initialization."""
        assert device_sensor._config_entry_id == "test_entry"
        assert device_sensor._device_name == "Test Device"
        assert device_sensor._device_id == "device_123"
        assert device_sensor._attr_should_poll is False
        assert device_sensor._attr_has_entity_name is True

    def test_device_info(self, device_sensor):
        """Test device info generation for individual device."""
        device_info = device_sensor.device_info
        
        assert isinstance(device_info, DeviceInfo)
        assert device_info["identifiers"] == {(DOMAIN, "device_123")}
        assert device_info["name"] == "Test Device"
        assert device_info["manufacturer"] == "Emporia"
        assert device_info["model"] == "Smart Plug"
        assert device_info["configuration_url"] is None

    def test_unique_id_not_implemented(self, device_sensor):
        """Test that unique_id must be implemented by subclasses."""
        with pytest.raises(NotImplementedError):
            _ = device_sensor.unique_id

    def test_inheritance_from_sensor_entity(self, device_sensor):
        """Test proper inheritance."""
        assert isinstance(device_sensor, SensorEntity)
        
        # Should have sensor entity properties
        assert hasattr(device_sensor, 'device_info')
        assert hasattr(device_sensor, 'should_poll')
        assert hasattr(device_sensor, 'has_entity_name')


class TestConcreteSensorImplementation:
    """Test concrete implementations of base sensors."""

    def test_concrete_base_sensor(self):
        """Test creating a concrete implementation of PhantomBaseSensor."""
        
        class ConcreteBaseSensor(PhantomBaseSensor):
            """Concrete implementation for testing."""
            
            @property
            def unique_id(self):
                """Return unique ID."""
                return f"{self._group_id}_test_sensor"
            
            @property
            def name(self):
                """Return name."""
                return "Test Sensor"
        
        sensor = ConcreteBaseSensor(
            config_entry_id="test",
            group_name="Group",
            group_id="group_1"
        )
        
        assert sensor.unique_id == "group_1_test_sensor"
        assert sensor.name == "Test Sensor"
        assert sensor.device_info["name"] == "Group"

    def test_concrete_device_sensor(self):
        """Test creating a concrete implementation of PhantomDeviceSensor."""
        
        class ConcreteDeviceSensor(PhantomDeviceSensor):
            """Concrete implementation for testing."""
            
            @property
            def unique_id(self):
                """Return unique ID."""
                return f"{self._device_id}_test_sensor"
            
            @property
            def name(self):
                """Return name."""
                return "Device Test Sensor"
        
        sensor = ConcreteDeviceSensor(
            config_entry_id="test",
            device_name="Device",
            device_id="device_1"
        )
        
        assert sensor.unique_id == "device_1_test_sensor"
        assert sensor.name == "Device Test Sensor"
        assert sensor.device_info["name"] == "Device"

    def test_sensor_entity_integration(self):
        """Test that base sensors integrate properly with Home Assistant."""
        
        class TestGroupSensor(PhantomBaseSensor):
            """Test group sensor."""
            
            @property
            def unique_id(self):
                return f"{self._group_id}_test"
            
            @property
            def name(self):
                return "Test"
            
            @property
            def native_value(self):
                return 42.0
        
        sensor = TestGroupSensor(
            config_entry_id="test",
            group_name="Test Group",
            group_id="group_123"
        )
        
        # Test Home Assistant integration properties
        assert sensor.should_poll is False
        assert sensor.has_entity_name is True
        assert sensor.native_value == 42.0
        
        # Test device registry integration
        device_info = sensor.device_info
        assert device_info["identifiers"] == {(DOMAIN, "group_123")}
        assert device_info["manufacturer"] == "Emporia"