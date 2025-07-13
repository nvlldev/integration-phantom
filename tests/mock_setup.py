"""Mock setup to handle all Home Assistant import issues."""
import sys
from unittest.mock import MagicMock, Mock

# Create comprehensive mocks for all HA modules
def setup_mocks():
    """Set up all necessary mocks before any imports."""
    
    # Mock all problematic homeassistant.components modules
    components_to_mock = [
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
    ]
    
    for module in components_to_mock:
        sys.modules[module] = MagicMock()
    
    # Set up specific attributes needed
    sys.modules['homeassistant.components'].frontend = MagicMock()
    sys.modules['homeassistant.components'].websocket_api = MagicMock()
    sys.modules['homeassistant.components'].http = MagicMock()
    sys.modules['homeassistant.components.http'].StaticPathConfig = MagicMock()
    
    # Mock other HA modules that might be needed
    sys.modules['homeassistant.util.async_'] = MagicMock()
    sys.modules['homeassistant.util'] = MagicMock()
    
    # Setup constants and enums
    from homeassistant import const
    if not hasattr(const, 'STATE_UNAVAILABLE'):
        const.STATE_UNAVAILABLE = 'unavailable'
    if not hasattr(const, 'STATE_UNKNOWN'):
        const.STATE_UNKNOWN = 'unknown'
    if not hasattr(const, 'UnitOfPower'):
        const.UnitOfPower = Mock(WATT='W')
    if not hasattr(const, 'UnitOfEnergy'):
        const.UnitOfEnergy = Mock(KILO_WATT_HOUR='kWh')


# Call setup before any other imports
setup_mocks()