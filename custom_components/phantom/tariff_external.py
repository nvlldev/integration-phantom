"""External tariff sensor support for Phantom Power Monitoring."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .tariff import TariffManager

_LOGGER = logging.getLogger(__name__)


class ExternalTariffManager(TariffManager):
    """Tariff manager that uses external sensors for rate and period."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        tariff_config: dict[str, Any] | None,
        rate_entity: str | None = None,
        period_entity: str | None = None,
    ) -> None:
        """Initialize external tariff manager."""
        super().__init__(tariff_config)
        self._hass = hass
        self._rate_entity = rate_entity
        self._period_entity = period_entity
        self._current_external_rate = None
        self._current_external_period = None
        self._listeners = []
        
    def setup(self) -> None:
        """Set up listeners for external sensors."""
        entities = []
        if self._rate_entity:
            entities.append(self._rate_entity)
        if self._period_entity:
            entities.append(self._period_entity)
            
        if entities:
            self._listeners.append(
                async_track_state_change_event(
                    self._hass,
                    entities,
                    self._handle_external_update,
                )
            )
            # Get initial values
            self._update_external_values()
            
    def cleanup(self) -> None:
        """Clean up listeners."""
        for listener in self._listeners:
            listener()
        self._listeners.clear()
        
    def _handle_external_update(self, event) -> None:
        """Handle updates from external sensors."""
        self._update_external_values()
        
    def _update_external_values(self) -> None:
        """Update values from external sensors."""
        if self._rate_entity:
            state = self._hass.states.get(self._rate_entity)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    self._current_external_rate = float(state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid rate value: %s", state.state)
                    
        if self._period_entity:
            state = self._hass.states.get(self._period_entity)
            if state and state.state not in ("unavailable", "unknown"):
                self._current_external_period = state.state
                
    def get_current_rate(self, now=None) -> float:
        """Get current rate from external sensor or fall back to configured."""
        if self._rate_entity and self._current_external_rate is not None:
            return self._current_external_rate
        return super().get_current_rate(now)
        
    def get_current_period(self, now=None) -> str | None:
        """Get current period from external sensor or fall back to configured."""
        if self._period_entity and self._current_external_period is not None:
            return self._current_external_period
        return super().get_current_period(now)