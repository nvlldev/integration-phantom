"""Tariff and Time-of-Use rate management for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any

from .const import (
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

_LOGGER = logging.getLogger(__name__)


class TariffManager:
    """Manages tariff rates and TOU period calculations."""
    
    def __init__(self, tariff_config: dict[str, Any] | None) -> None:
        """Initialize tariff manager."""
        self._config = tariff_config or {}
        self._enabled = self._config.get(CONF_TARIFF_ENABLED, False)
        self._currency = self._config.get(CONF_TARIFF_CURRENCY, "USD")
        self._currency_symbol = self._config.get(CONF_TARIFF_CURRENCY_SYMBOL, "$")
        self._rate_structure = self._config.get(CONF_TARIFF_RATE_STRUCTURE, {})
        
        # Validate configuration if enabled
        if self._enabled:
            self._validate_config()
        
    @property
    def enabled(self) -> bool:
        """Return if tariff tracking is enabled."""
        return self._enabled
        
    @property
    def currency(self) -> str:
        """Return the currency code."""
        return self._currency
        
    @property
    def currency_symbol(self) -> str:
        """Return the currency symbol."""
        return self._currency_symbol
        
    def get_current_rate(self, now: datetime | None = None) -> float:
        """Get the current electricity rate based on time and rate structure."""
        if not self._enabled:
            return 0.0
            
        rate_type = self._rate_structure.get(CONF_TARIFF_RATE_TYPE, TARIFF_TYPE_FLAT)
        
        if rate_type == TARIFF_TYPE_FLAT:
            return self._rate_structure.get(CONF_TARIFF_FLAT_RATE, 0.0)
        elif rate_type == TARIFF_TYPE_TOU:
            return self._get_tou_rate(now or datetime.now())
        
        return 0.0
        
    def get_current_period(self, now: datetime | None = None) -> str | None:
        """Get the current TOU period name."""
        if not self._enabled:
            return None
            
        rate_type = self._rate_structure.get(CONF_TARIFF_RATE_TYPE, TARIFF_TYPE_FLAT)
        
        if rate_type == TARIFF_TYPE_FLAT:
            return "flat"
        elif rate_type == TARIFF_TYPE_TOU:
            return self._get_tou_period(now or datetime.now())
        
        return None
        
    def _get_tou_rate(self, now: datetime) -> float:
        """Get TOU rate for the given time."""
        tou_rates = self._rate_structure.get(CONF_TARIFF_TOU_RATES, [])
        
        if not tou_rates:
            # If no TOU rates configured, fall back to flat rate
            return self._rate_structure.get(CONF_TARIFF_FLAT_RATE, 0.0)
        
        current_time = now.time()
        current_weekday = now.weekday()  # 0 = Monday, 6 = Sunday
        
        matched_rate = None
        for rate_config in tou_rates:
            # Check if today is included in this rate's days
            days = rate_config.get(CONF_TOU_DAYS, [])
            if days and current_weekday not in days:
                continue
                
            # Parse start and end times
            start_time_str = rate_config.get(CONF_TOU_START_TIME, "00:00")
            end_time_str = rate_config.get(CONF_TOU_END_TIME, "24:00")
            
            try:
                start_hour, start_min = map(int, start_time_str.split(":"))
                end_hour, end_min = map(int, end_time_str.split(":"))
                
                # Handle 24:00 as midnight next day
                if end_hour == 24 and end_min == 0:
                    # Check if we're in a period that ends at midnight
                    if start_hour < 24:
                        end_time = time(23, 59, 59)
                        start_time = time(start_hour, start_min)
                        if start_time <= current_time <= end_time:
                            matched_rate = rate_config.get(CONF_TOU_RATE, 0.0)
                            break
                else:
                    start_time = time(start_hour, start_min)
                    end_time = time(end_hour, end_min)
                    
                    # Check if current time is within this period
                    if start_time <= end_time:
                        # Normal case: period doesn't cross midnight
                        if start_time <= current_time <= end_time:
                            matched_rate = rate_config.get(CONF_TOU_RATE, 0.0)
                            break
                    else:
                        # Period crosses midnight (e.g., 22:00 to 06:00)
                        if current_time >= start_time or current_time <= end_time:
                            matched_rate = rate_config.get(CONF_TOU_RATE, 0.0)
                            break
                            
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Invalid time format in TOU rate config: %s - %s: %s",
                    start_time_str,
                    end_time_str,
                    err
                )
        
        if matched_rate is not None:
            return matched_rate
            
        # No matching rate found - use flat rate as fallback if available
        flat_rate = self._rate_structure.get(CONF_TARIFF_FLAT_RATE, 0.0)
        if flat_rate > 0:
            _LOGGER.debug("No TOU rate matched for %s, using flat rate: %s", now, flat_rate)
            return flat_rate
            
        _LOGGER.warning("No TOU rate found for time %s and no flat rate fallback", now)
        return 0.0
        
    def _get_tou_period(self, now: datetime) -> str | None:
        """Get TOU period name for the given time."""
        tou_rates = self._rate_structure.get(CONF_TARIFF_TOU_RATES, [])
        
        if not tou_rates:
            # If no TOU rates configured, return flat
            return "flat" if self._rate_structure.get(CONF_TARIFF_FLAT_RATE, 0.0) > 0 else None
        
        current_time = now.time()
        current_weekday = now.weekday()  # 0 = Monday, 6 = Sunday
        
        for rate_config in tou_rates:
            # Check if today is included in this rate's days
            days = rate_config.get(CONF_TOU_DAYS, [])
            if days and current_weekday not in days:
                continue
                
            # Parse start and end times
            start_time_str = rate_config.get(CONF_TOU_START_TIME, "00:00")
            end_time_str = rate_config.get(CONF_TOU_END_TIME, "24:00")
            
            try:
                start_hour, start_min = map(int, start_time_str.split(":"))
                end_hour, end_min = map(int, end_time_str.split(":"))
                
                # Handle 24:00 as midnight next day
                if end_hour == 24 and end_min == 0:
                    # Check if we're in a period that ends at midnight
                    if start_hour < 24:
                        end_time = time(23, 59, 59)
                        start_time = time(start_hour, start_min)
                        if start_time <= current_time <= end_time:
                            return rate_config.get(CONF_TOU_NAME, "unknown")
                else:
                    start_time = time(start_hour, start_min)
                    end_time = time(end_hour, end_min)
                    
                    # Check if current time is within this period
                    if start_time <= end_time:
                        # Normal case: period doesn't cross midnight
                        if start_time <= current_time <= end_time:
                            return rate_config.get(CONF_TOU_NAME, "unknown")
                    else:
                        # Period crosses midnight (e.g., 22:00 to 06:00)
                        if current_time >= start_time or current_time <= end_time:
                            return rate_config.get(CONF_TOU_NAME, "unknown")
                            
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Invalid time format in TOU rate config: %s - %s: %s",
                    start_time_str,
                    end_time_str,
                    err
                )
                
        # Check if flat rate is configured as fallback
        if self._rate_structure.get(CONF_TARIFF_FLAT_RATE, 0.0) > 0:
            return "flat"
            
        return None
        
    def calculate_cost_per_hour(self, power_watts: float, rate: float | None = None) -> float:
        """Calculate cost per hour for given power consumption."""
        if not self._enabled:
            return 0.0
            
        if rate is None:
            rate = self.get_current_rate()
            
        # Convert watts to kW and multiply by rate
        return (power_watts / 1000) * rate
        
    def calculate_energy_cost(self, energy_kwh: float, rate: float | None = None) -> float:
        """Calculate cost for given energy consumption."""
        if not self._enabled:
            return 0.0
            
        if rate is None:
            rate = self.get_current_rate()
            
        return energy_kwh * rate
        
    def _validate_config(self) -> None:
        """Validate tariff configuration."""
        rate_type = self._rate_structure.get(CONF_TARIFF_RATE_TYPE)
        
        if not rate_type:
            _LOGGER.warning("No rate type specified in tariff configuration")
            return
            
        if rate_type == TARIFF_TYPE_FLAT:
            flat_rate = self._rate_structure.get(CONF_TARIFF_FLAT_RATE, 0.0)
            if flat_rate <= 0:
                _LOGGER.warning("Flat rate tariff enabled but no valid rate specified")
        elif rate_type == TARIFF_TYPE_TOU:
            tou_rates = self._rate_structure.get(CONF_TARIFF_TOU_RATES, [])
            if not tou_rates:
                _LOGGER.warning("TOU tariff enabled but no rate periods defined")
            else:
                # Validate each TOU period
                for i, rate_config in enumerate(tou_rates):
                    if CONF_TOU_RATE not in rate_config:
                        _LOGGER.warning("TOU period %d missing rate", i)
                    if CONF_TOU_NAME not in rate_config:
                        _LOGGER.warning("TOU period %d missing name", i)
                    if CONF_TOU_START_TIME not in rate_config:
                        _LOGGER.warning("TOU period %d missing start time", i)
                    if CONF_TOU_END_TIME not in rate_config:
                        _LOGGER.warning("TOU period %d missing end time", i)