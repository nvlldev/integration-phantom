"""Tests for API functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from custom_components.phantom.api import (
    async_setup_api,
    ws_get_config,
    ws_save_config,
)
from custom_components.phantom.const import (
    DOMAIN,
    CONF_GROUPS,
    CONF_DEVICES,
    CONF_GROUP_NAME,
    CONF_GROUP_ID,
    CONF_DEVICE_ID,
    CONF_TARIFF,
)


def test_ws_get_config(mock_hass, mock_config_entry):
    """Test getting configuration via websocket."""
    # Setup mock data
    config_data = {
        CONF_GROUPS: [
            {
                CONF_GROUP_NAME: "Test Group",
                CONF_GROUP_ID: "group_123",
                CONF_DEVICES: [
                    {
                        "name": "Test Device",
                        "power_entity": "sensor.test_power",
                        "energy_entity": "sensor.test_energy",
                        CONF_DEVICE_ID: "device_123",
                    }
                ],
            }
        ],
        CONF_TARIFF: {
            "enabled": True,
            "currency": "USD",
        },
    }
    
    mock_hass.data[DOMAIN] = {
        mock_config_entry.entry_id: config_data
    }
    
    # Mock connection
    connection = MagicMock()
    connection.send_result = MagicMock()
    
    # Mock message
    msg = {
        "id": 123,
        "type": "phantom/get_config",
    }
    
    # Get config entry
    mock_hass.config_entries.async_entries.return_value = [mock_config_entry]
    
    # Call handler
    ws_get_config(mock_hass, connection, msg)
    
    # Verify response
    connection.send_result.assert_called_once()
    call_args = connection.send_result.call_args[0]
    assert call_args[0] == 123  # message id
    
    result = call_args[1]
    assert "groups" in result
    assert len(result["groups"]) == 1
    assert result["groups"][0][CONF_GROUP_NAME] == "Test Group"
    assert "tariff" in result
    assert result["tariff"]["enabled"] is True


def test_async_setup_api(mock_hass):
    """Test API setup."""
    # Mock the websocket_api module
    with patch('custom_components.phantom.api.websocket_api') as mock_ws_api:
        mock_ws_api.async_register_command = MagicMock()
        
        # Setup API
        async_setup_api(mock_hass)
        
        # Verify commands were registered
        assert mock_ws_api.async_register_command.call_count == 2
        
        # Verify it was called with the correct arguments
        calls = mock_ws_api.async_register_command.call_args_list
        assert len(calls) == 2
        # First call should register ws_get_config
        assert calls[0][0][0] == mock_hass
        # Second call should register ws_save_config
        assert calls[1][0][0] == mock_hass