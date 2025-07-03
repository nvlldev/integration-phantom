"""Tests for tariff functionality."""
import pytest
from datetime import datetime, time
from unittest.mock import MagicMock, patch

from custom_components.phantom.tariff import TariffManager
from custom_components.phantom.tariff_external import ExternalTariffManager
from custom_components.phantom.const import (
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


class TestTariffManager:
    """Test the TariffManager class."""

    def test_init_with_empty_config(self):
        """Test initialization with empty configuration."""
        manager = TariffManager(None)
        assert not manager.enabled
        assert manager.currency == "USD"
        assert manager.currency_symbol == "$"
        assert manager.get_current_rate() == 0.0
        assert manager.get_current_period() is None

    def test_init_with_flat_rate(self, sample_flat_tariff_config):
        """Test initialization with flat rate configuration."""
        manager = TariffManager(sample_flat_tariff_config)
        assert manager.enabled
        assert manager.currency == "USD"
        assert manager.currency_symbol == "$"
        assert manager.get_current_rate() == 0.15
        assert manager.get_current_period() == "flat"

    def test_init_with_tou_rates(self, sample_tou_tariff_config):
        """Test initialization with TOU rate configuration."""
        manager = TariffManager(sample_tou_tariff_config)
        assert manager.enabled
        assert manager.currency == "USD"
        assert manager.currency_symbol == "$"

    def test_flat_rate_calculation(self, sample_flat_tariff_config):
        """Test flat rate calculations."""
        manager = TariffManager(sample_flat_tariff_config)
        
        # Test rate retrieval
        assert manager.get_current_rate() == 0.15
        
        # Test cost per hour calculation
        power_watts = 1000  # 1 kW
        cost_per_hour = manager.calculate_cost_per_hour(power_watts)
        assert cost_per_hour == 0.15  # 1 kW * $0.15/kWh
        
        # Test energy cost calculation
        energy_kwh = 10
        cost = manager.calculate_energy_cost(energy_kwh)
        assert cost == 1.5  # 10 kWh * $0.15/kWh

    def test_tou_rate_weekday_peak(self, sample_tou_tariff_config):
        """Test TOU rate during weekday peak hours."""
        manager = TariffManager(sample_tou_tariff_config)
        
        # Monday at 6 PM (peak time)
        test_time = datetime(2024, 1, 1, 18, 0)  # Monday
        with patch('custom_components.phantom.tariff.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time
            assert manager.get_current_rate(test_time) == 0.30
            assert manager.get_current_period(test_time) == "Peak"

    def test_tou_rate_weekday_off_peak(self, sample_tou_tariff_config):
        """Test TOU rate during weekday off-peak hours."""
        manager = TariffManager(sample_tou_tariff_config)
        
        # Monday at 10 PM (off-peak time)
        test_time = datetime(2024, 1, 1, 22, 0)  # Monday
        assert manager.get_current_rate(test_time) == 0.10
        assert manager.get_current_period(test_time) == "Off-Peak"

    def test_tou_rate_weekend(self, sample_tou_tariff_config):
        """Test TOU rate during weekend."""
        manager = TariffManager(sample_tou_tariff_config)
        
        # Saturday at 6 PM (weekend, should be off-peak since peak is weekdays only)
        test_time = datetime(2024, 1, 6, 18, 0)  # Saturday (weekday=5)
        # Note: The off-peak period in the test config covers 21:00-17:00, 
        # so 18:00 (6 PM) is not in the off-peak period either
        # We need to check a time that's actually in the off-peak period
        test_time = datetime(2024, 1, 6, 22, 0)  # Saturday at 10 PM
        assert manager.get_current_rate(test_time) == 0.10
        assert manager.get_current_period(test_time) == "Off-Peak"

    def test_tou_rate_midnight_crossing(self):
        """Test TOU rate for periods crossing midnight."""
        config = {
            CONF_TARIFF_ENABLED: True,
            CONF_TARIFF_CURRENCY: "USD",
            CONF_TARIFF_CURRENCY_SYMBOL: "$",
            CONF_TARIFF_RATE_STRUCTURE: {
                CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_TOU,
                CONF_TARIFF_TOU_RATES: [
                    {
                        CONF_TOU_NAME: "Night",
                        CONF_TOU_RATE: 0.08,
                        CONF_TOU_START_TIME: "22:00",
                        CONF_TOU_END_TIME: "06:00",
                        CONF_TOU_DAYS: [0, 1, 2, 3, 4, 5, 6],
                    },
                    {
                        CONF_TOU_NAME: "Day",
                        CONF_TOU_RATE: 0.20,
                        CONF_TOU_START_TIME: "06:00",
                        CONF_TOU_END_TIME: "22:00",
                        CONF_TOU_DAYS: [0, 1, 2, 3, 4, 5, 6],
                    },
                ]
            }
        }
        manager = TariffManager(config)
        
        # Test at 11 PM (should be night rate)
        test_time = datetime(2024, 1, 1, 23, 0)
        assert manager.get_current_rate(test_time) == 0.08
        assert manager.get_current_period(test_time) == "Night"
        
        # Test at 2 AM (should still be night rate)
        test_time = datetime(2024, 1, 2, 2, 0)
        assert manager.get_current_rate(test_time) == 0.08
        assert manager.get_current_period(test_time) == "Night"

    def test_tou_no_matching_period(self):
        """Test TOU when no period matches."""
        config = {
            CONF_TARIFF_ENABLED: True,
            CONF_TARIFF_CURRENCY: "USD",
            CONF_TARIFF_CURRENCY_SYMBOL: "$",
            CONF_TARIFF_RATE_STRUCTURE: {
                CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_TOU,
                CONF_TARIFF_FLAT_RATE: 0.12,  # Fallback rate
                CONF_TARIFF_TOU_RATES: [
                    {
                        CONF_TOU_NAME: "Weekday",
                        CONF_TOU_RATE: 0.20,
                        CONF_TOU_START_TIME: "09:00",
                        CONF_TOU_END_TIME: "17:00",
                        CONF_TOU_DAYS: [0, 1, 2, 3, 4],  # Weekdays only
                    },
                ]
            }
        }
        manager = TariffManager(config)
        
        # Saturday (not in any TOU period)
        test_time = datetime(2024, 1, 6, 12, 0)
        assert manager.get_current_rate(test_time) == 0.12  # Falls back to flat rate
        assert manager.get_current_period(test_time) == "flat"

    def test_disabled_tariff(self):
        """Test behavior when tariff is disabled."""
        config = {
            CONF_TARIFF_ENABLED: False,
            CONF_TARIFF_RATE_STRUCTURE: {
                CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_FLAT,
                CONF_TARIFF_FLAT_RATE: 0.15,
            }
        }
        manager = TariffManager(config)
        
        assert not manager.enabled
        assert manager.get_current_rate() == 0.0
        assert manager.get_current_period() is None
        assert manager.calculate_cost_per_hour(1000) == 0.0
        assert manager.calculate_energy_cost(10) == 0.0

    def test_invalid_time_format(self, caplog):
        """Test handling of invalid time formats."""
        config = {
            CONF_TARIFF_ENABLED: True,
            CONF_TARIFF_RATE_STRUCTURE: {
                CONF_TARIFF_RATE_TYPE: TARIFF_TYPE_TOU,
                CONF_TARIFF_TOU_RATES: [
                    {
                        CONF_TOU_NAME: "Invalid",
                        CONF_TOU_RATE: 0.20,
                        CONF_TOU_START_TIME: "25:00",  # Invalid hour
                        CONF_TOU_END_TIME: "30:00",
                        CONF_TOU_DAYS: [0, 1, 2, 3, 4],
                    },
                ]
            }
        }
        manager = TariffManager(config)
        
        # Should handle error gracefully
        assert manager.get_current_rate() == 0.0
        assert "Invalid time format" in caplog.text


class TestExternalTariffManager:
    """Test the ExternalTariffManager class."""

    def test_init_external_manager(self, mock_hass, sample_external_tariff_config):
        """Test initialization of external tariff manager."""
        manager = ExternalTariffManager(
            mock_hass,
            sample_external_tariff_config,
            "sensor.electricity_rate",
            "sensor.tou_period"
        )
        
        assert manager._rate_entity == "sensor.electricity_rate"
        assert manager._period_entity == "sensor.tou_period"
        assert manager._current_external_rate is None
        assert manager._current_external_period is None

    def test_external_rate_update(self, mock_hass, sample_external_tariff_config, mock_state):
        """Test external rate sensor updates."""
        manager = ExternalTariffManager(
            mock_hass,
            sample_external_tariff_config,
            "sensor.electricity_rate",
            None
        )
        
        # Mock external rate sensor
        rate_state = mock_state("sensor.electricity_rate", "0.25")
        mock_hass.states.get.return_value = rate_state
        
        # Update external values
        manager._update_external_values()
        
        # Should use external rate
        assert manager.get_current_rate() == 0.25

    def test_external_period_update(self, mock_hass, sample_external_tariff_config, mock_state):
        """Test external period sensor updates."""
        manager = ExternalTariffManager(
            mock_hass,
            sample_external_tariff_config,
            None,
            "sensor.tou_period"
        )
        
        # Mock external period sensor
        period_state = mock_state("sensor.tou_period", "Peak Hours")
        mock_hass.states.get.return_value = period_state
        
        # Update external values
        manager._update_external_values()
        
        # Should use external period
        assert manager.get_current_period() == "Peak Hours"

    def test_external_fallback_to_internal(self, mock_hass, sample_flat_tariff_config):
        """Test fallback to internal rates when external not available."""
        # Add external config to flat rate config
        config = sample_flat_tariff_config.copy()
        config["rate_entity"] = "sensor.electricity_rate"
        
        manager = ExternalTariffManager(
            mock_hass,
            config,
            "sensor.electricity_rate",
            None
        )
        
        # No external rate available
        mock_hass.states.get.return_value = None
        manager._update_external_values()
        
        # Should fall back to internal flat rate
        assert manager.get_current_rate() == 0.15

    def test_cleanup(self, mock_hass, sample_external_tariff_config):
        """Test cleanup of listeners."""
        manager = ExternalTariffManager(
            mock_hass,
            sample_external_tariff_config,
            "sensor.electricity_rate",
            None
        )
        
        # Mock listener
        mock_listener = MagicMock()
        manager._listeners = [mock_listener]
        
        # Cleanup should call all listeners
        manager.cleanup()
        mock_listener.assert_called_once()
        assert len(manager._listeners) == 0