"""Tests for the accumulated cost remainder sensor."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, Event, State
from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.event import EventStateChangedData

from custom_components.phantom.sensors.remainder_cost import PhantomCostRemainderSensor
from custom_components.phantom.tariff import TariffManager


class TestPhantomCostRemainderSensor:
    """Test the PhantomCostRemainderSensor functionality."""

    @pytest.fixture
    def mock_tariff_manager(self):
        """Create a mock tariff manager."""
        manager = MagicMock(spec=TariffManager)
        manager.currency = "USD"
        manager.currency_symbol = "$"
        return manager

    @pytest.fixture
    def cost_remainder_sensor(self, mock_hass, mock_tariff_manager):
        """Create a cost remainder sensor instance."""
        return PhantomCostRemainderSensor(
            hass=mock_hass,
            config_entry_id="test_entry",
            group_name="Test Group",
            group_id="group_123",
            upstream_cost_entity="sensor.upstream_cost",
            group_total_cost_entity="sensor.group_total_cost",
            tariff_manager=mock_tariff_manager,
        )

    def test_init(self, cost_remainder_sensor, mock_tariff_manager):
        """Test sensor initialization."""
        assert cost_remainder_sensor._attr_name == "Cost Remainder"
        assert cost_remainder_sensor._attr_state_class == SensorStateClass.TOTAL_INCREASING
        assert cost_remainder_sensor._attr_native_unit_of_measurement == "USD"
        assert cost_remainder_sensor._attr_icon == "mdi:cash-minus"
        assert cost_remainder_sensor._attr_suggested_display_precision == 2
        assert cost_remainder_sensor._accumulated_remainder == 0.0
        assert cost_remainder_sensor._last_upstream_value is None
        assert cost_remainder_sensor._last_total_value is None

    def test_extra_state_attributes(self, cost_remainder_sensor):
        """Test extra state attributes."""
        cost_remainder_sensor._accumulated_remainder = 0.06
        cost_remainder_sensor._last_upstream_value = 0.13
        cost_remainder_sensor._last_total_value = 0.07
        
        attrs = cost_remainder_sensor.extra_state_attributes
        
        assert attrs["currency_symbol"] == "$"
        assert attrs["upstream_cost_entity"] == "sensor.upstream_cost"
        assert attrs["group_total_cost_entity"] == "sensor.group_total_cost"
        assert attrs["accumulated_remainder"] == 0.06
        assert attrs["instantaneous_remainder"] == 0.06  # 0.13 - 0.07
        assert attrs["instantaneous_remainder_percent"] == pytest.approx(46.15, rel=0.01)  # (0.06/0.13)*100
        assert attrs["last_upstream_value"] == 0.13
        assert attrs["last_total_value"] == 0.07

    def test_extra_state_attributes_no_upstream_value(self, cost_remainder_sensor):
        """Test extra state attributes when upstream value is zero."""
        cost_remainder_sensor._accumulated_remainder = 0.0
        cost_remainder_sensor._last_upstream_value = 0.0
        cost_remainder_sensor._last_total_value = 0.0
        
        attrs = cost_remainder_sensor.extra_state_attributes
        
        assert attrs["instantaneous_remainder"] == 0.0
        assert attrs["instantaneous_remainder_percent"] == 0.0

    @pytest.mark.asyncio
    async def test_async_added_to_hass_restore_state(self, cost_remainder_sensor, mock_hass):
        """Test restoring state when added to hass."""
        # Mock last state
        mock_last_state = MagicMock(spec=State)
        mock_last_state.state = "0.05"
        mock_last_state.attributes = {
            "last_upstream_value": 0.10,
            "last_total_value": 0.05,
        }
        
        cost_remainder_sensor.async_on_remove = MagicMock()
        cost_remainder_sensor.async_get_last_state = AsyncMock(return_value=mock_last_state)
        
        with patch("custom_components.phantom.sensors.remainder_cost.async_track_state_change_event"):
            await cost_remainder_sensor.async_added_to_hass()
        
        assert cost_remainder_sensor._accumulated_remainder == 0.05
        assert cost_remainder_sensor._attr_native_value == 0.05
        assert cost_remainder_sensor._last_upstream_value == 0.10
        assert cost_remainder_sensor._last_total_value == 0.05

    @pytest.mark.asyncio
    async def test_async_added_to_hass_no_restore(self, cost_remainder_sensor, mock_hass):
        """Test initialization when no state to restore."""
        cost_remainder_sensor.async_on_remove = MagicMock()
        cost_remainder_sensor.async_get_last_state = AsyncMock(return_value=None)
        
        with patch("custom_components.phantom.sensors.remainder_cost.async_track_state_change_event"):
            await cost_remainder_sensor.async_added_to_hass()
        
        assert cost_remainder_sensor._accumulated_remainder == 0.0
        assert cost_remainder_sensor._attr_native_value == 0.0
        assert cost_remainder_sensor._last_upstream_value is None
        assert cost_remainder_sensor._last_total_value is None

    def test_update_state_first_run(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test first run initialization."""
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.13"),
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.07"),
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should initialize tracking values but not accumulate
        assert cost_remainder_sensor._last_upstream_value == 0.13
        assert cost_remainder_sensor._last_total_value == 0.07
        assert cost_remainder_sensor._accumulated_remainder == 0.0
        assert cost_remainder_sensor._attr_native_value == 0.0

    def test_update_state_positive_remainder_accumulation(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test accumulating positive remainder."""
        # Set previous values
        cost_remainder_sensor._last_upstream_value = 0.10
        cost_remainder_sensor._last_total_value = 0.05
        cost_remainder_sensor._accumulated_remainder = 0.0
        
        # Mock states with increases
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.13"),  # +0.03
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.07"),  # +0.02
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should accumulate the positive remainder: (0.03 - 0.02) = 0.01
        assert cost_remainder_sensor._accumulated_remainder == 0.01
        assert cost_remainder_sensor._attr_native_value == 0.01
        assert cost_remainder_sensor._last_upstream_value == 0.13
        assert cost_remainder_sensor._last_total_value == 0.07

    def test_update_state_negative_remainder_not_accumulated(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test that negative remainder is not accumulated."""
        # Set previous values
        cost_remainder_sensor._last_upstream_value = 0.10
        cost_remainder_sensor._last_total_value = 0.05
        cost_remainder_sensor._accumulated_remainder = 0.02
        
        # Mock states where total increased more than upstream
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.11"),  # +0.01
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.08"),  # +0.03
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should not accumulate negative remainder: (0.01 - 0.03) = -0.02
        assert cost_remainder_sensor._accumulated_remainder == 0.02  # Unchanged
        assert cost_remainder_sensor._attr_native_value == 0.02

    def test_update_state_meter_reset(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test handling meter reset."""
        # Set previous values
        cost_remainder_sensor._last_upstream_value = 0.50
        cost_remainder_sensor._last_total_value = 0.45
        cost_remainder_sensor._accumulated_remainder = 0.05
        
        # Mock states with reset
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.02"),  # Reset
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.01"),  # Reset
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should handle reset without changing accumulated value
        assert cost_remainder_sensor._accumulated_remainder == 0.05  # Unchanged
        assert cost_remainder_sensor._attr_native_value == 0.05
        assert cost_remainder_sensor._last_upstream_value == 0.02
        assert cost_remainder_sensor._last_total_value == 0.01

    def test_update_state_sanity_check(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test sanity check prevents accumulated > instantaneous remainder."""
        # Set accumulated remainder higher than it should be
        cost_remainder_sensor._last_upstream_value = 0.10
        cost_remainder_sensor._last_total_value = 0.05
        cost_remainder_sensor._accumulated_remainder = 0.10  # Too high!
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.13"),
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.07"),
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should reset to instantaneous remainder: 0.13 - 0.07 = 0.06
        assert cost_remainder_sensor._accumulated_remainder == 0.06
        assert cost_remainder_sensor._attr_native_value == 0.06

    def test_update_state_upstream_unavailable(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test handling upstream unavailable."""
        cost_remainder_sensor._accumulated_remainder = 0.05
        cost_remainder_sensor._attr_available = True
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", STATE_UNAVAILABLE),
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.07"),
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should maintain current value
        assert cost_remainder_sensor._accumulated_remainder == 0.05
        assert cost_remainder_sensor._attr_native_value == 0.05

    def test_update_state_total_unavailable(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test handling total cost unavailable."""
        cost_remainder_sensor._accumulated_remainder = 0.05
        cost_remainder_sensor._attr_available = True
        
        # Mock states
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.13"),
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", STATE_UNKNOWN),
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should maintain current value
        assert cost_remainder_sensor._accumulated_remainder == 0.05
        assert cost_remainder_sensor._attr_native_value == 0.05

    def test_handle_state_change(self, cost_remainder_sensor):
        """Test state change event handler."""
        cost_remainder_sensor._update_state = MagicMock()
        cost_remainder_sensor.async_write_ha_state = MagicMock()
        
        # Create mock event
        mock_event = MagicMock(spec=Event)
        mock_new_state = MagicMock()
        mock_event.data = {"new_state": mock_new_state}
        
        cost_remainder_sensor._handle_state_change(mock_event)
        
        cost_remainder_sensor._update_state.assert_called_once()
        cost_remainder_sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_reset(self, cost_remainder_sensor):
        """Test resetting the sensor."""
        # Set some values
        cost_remainder_sensor._accumulated_remainder = 0.05
        cost_remainder_sensor._last_upstream_value = 0.13
        cost_remainder_sensor._last_total_value = 0.07
        cost_remainder_sensor._attr_native_value = 0.05
        
        cost_remainder_sensor._update_state = MagicMock()
        cost_remainder_sensor.async_write_ha_state = MagicMock()
        
        await cost_remainder_sensor.async_reset()
        
        # Should reset all values
        assert cost_remainder_sensor._accumulated_remainder == 0.0
        assert cost_remainder_sensor._attr_native_value == 0.0
        assert cost_remainder_sensor._last_upstream_value is None
        assert cost_remainder_sensor._last_total_value is None
        cost_remainder_sensor._update_state.assert_called_once()
        cost_remainder_sensor.async_write_ha_state.assert_called_once()

    def test_precision_handling(self, cost_remainder_sensor, mock_hass, mock_state):
        """Test that full precision is maintained in calculations."""
        # Set previous values with high precision
        cost_remainder_sensor._last_upstream_value = 0.123456789
        cost_remainder_sensor._last_total_value = 0.076543210
        cost_remainder_sensor._accumulated_remainder = 0.0
        
        # Mock states with small increases
        mock_hass.states.get.side_effect = lambda entity_id: {
            "sensor.upstream_cost": mock_state("sensor.upstream_cost", "0.123456999"),  # +0.00000021
            "sensor.group_total_cost": mock_state("sensor.group_total_cost", "0.076543310"),  # +0.0000001
        }.get(entity_id)
        
        cost_remainder_sensor._update_state()
        
        # Should accumulate the tiny positive remainder with full precision
        expected_remainder = 0.00000021 - 0.0000001  # 0.00000011
        assert cost_remainder_sensor._accumulated_remainder == pytest.approx(expected_remainder, abs=1e-9)
        assert cost_remainder_sensor._last_upstream_value == 0.123456999
        assert cost_remainder_sensor._last_total_value == 0.076543310