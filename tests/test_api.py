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


@pytest.mark.asyncio
async def test_ws_save_config(mock_hass, mock_config_entry):
    """Test saving configuration via websocket."""
    # Setup initial data
    mock_hass.data[DOMAIN] = {
        mock_config_entry.entry_id: {
            CONF_GROUPS: []
        }
    }
    
    # Mock connection
    connection = MagicMock()
    connection.send_result = MagicMock()
    connection.send_error = MagicMock()
    
    # Mock message with new configuration
    msg = {
        "id": 456,
        "type": "phantom/save_config",
        "groups": [
            {
                CONF_GROUP_NAME: "New Group",
                CONF_DEVICES: [
                    {
                        "name": "New Device",
                        "power_entity": "sensor.new_power",
                        "energy_entity": "sensor.new_energy",
                    }
                ],
            }
        ],
        "tariff": {
            "enabled": False,
        },
    }
    
    # Mock config entries
    mock_hass.config_entries.async_entries.return_value = [mock_config_entry]
    mock_hass.config_entries.async_update_entry = MagicMock()
    mock_hass.config_entries.async_reload = AsyncMock()
    
    # Mock entity states
    mock_hass.states.get.return_value = MagicMock(
        state="100",
        attributes={"device_class": "power"}
    )
    
    # Mock UUID generation
    with patch('uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-567812345678')):
        # Call handler
        await ws_save_config(mock_hass, connection, msg)
    
    # Verify configuration was updated
    mock_hass.config_entries.async_update_entry.assert_called_once()
    updated_data = mock_hass.config_entries.async_update_entry.call_args[1]["data"]
    
    assert len(updated_data[CONF_GROUPS]) == 1
    assert updated_data[CONF_GROUPS][0][CONF_GROUP_NAME] == "New Group"
    assert updated_data[CONF_GROUPS][0][CONF_GROUP_ID] is not None
    assert len(updated_data[CONF_GROUPS][0][CONF_DEVICES]) == 1
    
    # Verify success response
    connection.send_result.assert_called_once_with(456, {"success": True})
    
    # Verify reload was triggered
    mock_hass.config_entries.async_reload.assert_called_once()


@pytest.mark.asyncio
async def test_ws_save_config_validation(mock_hass, mock_config_entry):
    """Test configuration validation during save."""
    # Setup initial data
    mock_hass.data[DOMAIN] = {
        mock_config_entry.entry_id: {
            CONF_GROUPS: []
        }
    }
    
    # Mock connection
    connection = MagicMock()
    connection.send_error = MagicMock()
    
    # Mock message with invalid configuration (empty group name)
    msg = {
        "id": 789,
        "type": "phantom/save_config",
        "groups": [
            {
                CONF_GROUP_NAME: "",  # Invalid empty name
                CONF_DEVICES: [],
            }
        ],
    }
    
    # Mock config entries
    mock_hass.config_entries.async_entries.return_value = [mock_config_entry]
    
    # Call handler
    await ws_save_config(mock_hass, connection, msg)
    
    # Verify error was sent
    connection.send_error.assert_called_once()
    error_args = connection.send_error.call_args[0]
    assert error_args[0] == 789  # message id
    assert "invalid_format" in error_args[1]  # error code




def test_async_setup_api(mock_hass):
    """Test API setup."""
    # Mock websocket API
    mock_hass.components = MagicMock()
    mock_hass.components.websocket_api = MagicMock()
    mock_hass.components.websocket_api.async_register_command = MagicMock()
    
    # Setup API
    async_setup_api(mock_hass)
    
    # Verify commands were registered
    assert mock_hass.components.websocket_api.async_register_command.call_count == 2
    
    # Verify command names
    call_args = mock_hass.components.websocket_api.async_register_command.call_args_list
    assert len(call_args) == 2