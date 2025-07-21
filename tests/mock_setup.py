"""Mock setup to handle all Home Assistant import issues."""
import sys
from unittest.mock import MagicMock, Mock

# Create comprehensive mocks for all HA modules
def setup_mocks():
    """Set up all necessary mocks before any imports."""
    
    # First, mock homeassistant.util and its submodules
    sys.modules['homeassistant.util'] = MagicMock()
    sys.modules['homeassistant.util.event_type'] = MagicMock()
    sys.modules['homeassistant.util.async_'] = MagicMock()
    
    # Create EventType mock
    EventType = MagicMock()
    sys.modules['homeassistant.util.event_type'].EventType = EventType
    
    # Mock homeassistant.const before it's imported
    const_mock = MagicMock()
    const_mock.STATE_UNAVAILABLE = 'unavailable'
    const_mock.STATE_UNKNOWN = 'unknown'
    const_mock.UnitOfPower = Mock(WATT='W')
    const_mock.UnitOfEnergy = Mock(KILO_WATT_HOUR='kWh')
    sys.modules['homeassistant.const'] = const_mock
    
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
    
    # Mock homeassistant.core
    core_mock = MagicMock()
    core_mock.HomeAssistant = MagicMock
    core_mock.State = MagicMock
    core_mock.Event = MagicMock
    sys.modules['homeassistant.core'] = core_mock
    
    # Mock homeassistant.components.sensor
    sensor_mock = MagicMock()
    sensor_mock.SensorEntity = MagicMock
    sensor_mock.SensorStateClass = MagicMock()
    sensor_mock.SensorDeviceClass = MagicMock()
    sys.modules['homeassistant.components.sensor'] = sensor_mock
    
    # Mock homeassistant.helpers modules
    sys.modules['homeassistant.helpers'] = MagicMock()
    sys.modules['homeassistant.helpers.entity'] = MagicMock()
    sys.modules['homeassistant.helpers.entity'].Entity = MagicMock
    sys.modules['homeassistant.helpers.restore_state'] = MagicMock()
    sys.modules['homeassistant.helpers.restore_state'].RestoreEntity = MagicMock
    sys.modules['homeassistant.helpers.entity_registry'] = MagicMock()


# Call setup before any other imports
setup_mocks()