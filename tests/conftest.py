"""Test configuration with comprehensive mocking."""
# Import mock setup first - this must be before any HA imports
from .mock_setup import setup_mocks
setup_mocks()

import sys
from unittest.mock import MagicMock, Mock
import pytest
from datetime import datetime

# Now we can safely import HA modules
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, State, Event
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er

# Mock panel to avoid import issues
sys.modules['custom_components.phantom.panel'] = MagicMock()

# Now import our constants
from custom_components.phantom.const import (
    DOMAIN,
    CONF_NAME,
    CONF_UTILITY_METER_NAME,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_GROUP_DEVICES,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_ENERGY_RATE,
    CONF_TOU_RATES,
    ATTR_ENTRIES,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.data = {}
    hass.bus = MagicMock()
    hass.async_create_task = MagicMock()
    hass.config = MagicMock()
    hass.config.units = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=None)
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        CONF_NAME: "Test Integration",
        CONF_UTILITY_METER_NAME: "sensor.utility_meter",
        CONF_DEVICES: [
            {
                CONF_NAME: "Device 1",
                CONF_DEVICE_ID: "device1_id",
            },
            {
                CONF_NAME: "Device 2", 
                CONF_DEVICE_ID: "device2_id",
            },
        ],
        CONF_GROUP_DEVICES: [
            {
                CONF_GROUP_NAME: "Group 1",
                CONF_GROUP_ID: "group1_id",
                CONF_DEVICES: ["device1_id", "device2_id"],
            }
        ],
        CONF_ENERGY_RATE: 0.12,
        CONF_TOU_RATES: [],
    }
    entry.options = {}
    entry.title = "Test Integration"
    entry.unique_id = "test_unique_id"
    return entry


@pytest.fixture
def mock_state():
    """Create a mock state factory."""
    def _create_state(entity_id, state, attributes=None):
        mock = MagicMock(spec=State)
        mock.entity_id = entity_id
        mock.state = state
        mock.attributes = attributes or {}
        mock.last_changed = datetime.now()
        mock.last_updated = datetime.now()
        return mock
    return _create_state


@pytest.fixture  
def mock_entity_registry():
    """Create a mock entity registry."""
    registry = MagicMock()
    registry.entities = {}
    registry.async_get = MagicMock(return_value=registry)
    return registry


@pytest.fixture
def mock_device_registry():
    """Create a mock device registry."""
    registry = MagicMock()
    registry.devices = {}
    registry.async_get = MagicMock(return_value=registry)
    return registry


@pytest.fixture
def mock_tariff_manager():
    """Create a mock tariff manager."""
    manager = MagicMock()
    manager.currency = "USD"
    manager.currency_symbol = "$"
    manager.get_current_rate = MagicMock(return_value=0.15)
    manager.get_current_period_info = MagicMock(return_value=None)
    return manager


@pytest.fixture
def mock_coordinator():
    """Create a mock data update coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "devices": {},
        "groups": {},
    }
    coordinator.async_request_refresh = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.last_update_success = True
    return coordinator