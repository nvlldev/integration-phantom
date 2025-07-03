"""Common fixtures for Phantom Power Monitoring tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from custom_components.phantom.const import (
    DOMAIN,
    CONF_GROUPS,
    CONF_DEVICES,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_DEVICE_ID,
    CONF_UPSTREAM_POWER_ENTITY,
    CONF_UPSTREAM_ENERGY_ENTITY,
    CONF_TARIFF,
    CONF_TARIFF_ENABLED,
    CONF_TARIFF_CURRENCY,
    CONF_TARIFF_CURRENCY_SYMBOL,
    CONF_TARIFF_RATE_STRUCTURE,
    CONF_TARIFF_RATE_TYPE,
    CONF_TARIFF_FLAT_RATE,
    CONF_TARIFF_TOU_RATES,
    CONF_TOU_NAME,
    CONF_TOU_RATE,
    CONF_TOU_START_TIME,
    CONF_TOU_END_TIME,
    CONF_TOU_DAYS,
    TARIFF_TYPE_FLAT,
    TARIFF_TYPE_TOU,
)


@pytest.fixture
def mock_hass():
    """Return a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.data = {DOMAIN: {}}
    hass.async_create_task = MagicMock()
    hass.helpers = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    entry.options = {}
    return entry


@pytest.fixture
def sample_device_config():
    """Return sample device configuration."""
    return {
        "name": "Test Device",
        "power_entity": "sensor.test_power",
        "energy_entity": "sensor.test_energy",
        CONF_DEVICE_ID: "device_123",
    }


@pytest.fixture
def sample_group_config(sample_device_config):
    """Return sample group configuration."""
    return {
        CONF_GROUP_NAME: "Test Group",
        CONF_GROUP_ID: "group_123",
        CONF_DEVICES: [sample_device_config],
        CONF_UPSTREAM_POWER_ENTITY: "sensor.upstream_power",
        CONF_UPSTREAM_ENERGY_ENTITY: "sensor.upstream_energy",
    }


@pytest.fixture
def sample_flat_tariff_config():
    """Return sample flat rate tariff configuration."""
    return {
        CONF_TARIFF_ENABLED: True,
        CONF_TARIFF_CURRENCY: "USD",
        CONF_TARIFF_CURRENCY_SYMBOL: "$",
        CONF_TARIFF_RATE_STRUCTURE: {
            CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_FLAT,
            CONF_TARIFF_FLAT_RATE: 0.15,
        }
    }


@pytest.fixture
def sample_tou_tariff_config():
    """Return sample TOU tariff configuration."""
    return {
        CONF_TARIFF_ENABLED: True,
        CONF_TARIFF_CURRENCY: "USD",
        CONF_TARIFF_CURRENCY_SYMBOL: "$",
        CONF_TARIFF_RATE_STRUCTURE: {
            CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_TOU,
            CONF_TARIFF_TOU_RATES: [
                {
                    CONF_TOU_NAME: "Peak",
                    CONF_TOU_RATE: 0.30,
                    CONF_TOU_START_TIME: "17:00",
                    CONF_TOU_END_TIME: "21:00",
                    CONF_TOU_DAYS: [0, 1, 2, 3, 4],  # Weekdays
                },
                {
                    CONF_TOU_NAME: "Off-Peak",
                    CONF_TOU_RATE: 0.10,
                    CONF_TOU_START_TIME: "21:00",
                    CONF_TOU_END_TIME: "17:00",
                    CONF_TOU_DAYS: [0, 1, 2, 3, 4, 5, 6],  # All days
                },
            ]
        }
    }


@pytest.fixture
def sample_external_tariff_config():
    """Return sample external tariff configuration."""
    return {
        CONF_TARIFF_ENABLED: True,
        CONF_TARIFF_CURRENCY: "USD",
        CONF_TARIFF_CURRENCY_SYMBOL: "$",
        "rate_entity": "sensor.electricity_rate",
        "period_entity": "sensor.tou_period",
    }


@pytest.fixture
def mock_state():
    """Return a mock state object."""
    def _mock_state(entity_id, state, attributes=None):
        mock = MagicMock()
        mock.entity_id = entity_id
        mock.state = state
        mock.attributes = attributes or {}
        return mock
    return _mock_state


@pytest.fixture
def mock_entity_registry():
    """Return a mock entity registry."""
    registry = MagicMock()
    registry.entities = {}
    return registry