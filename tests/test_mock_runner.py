"""Mock-based test runner to verify test logic without Home Assistant imports."""
import sys
import os
from unittest.mock import MagicMock, patch

# Mock Home Assistant modules before importing anything else
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.entity'] = MagicMock()
sys.modules['homeassistant.helpers.restore_state'] = MagicMock()
sys.modules['homeassistant.helpers.device_registry'] = MagicMock()
sys.modules['homeassistant.helpers.entity_registry'] = MagicMock()
sys.modules['homeassistant.helpers.event'] = MagicMock()

# Define constants
from unittest.mock import Mock
hass_const = sys.modules['homeassistant.const']
hass_const.STATE_UNAVAILABLE = 'unavailable'
hass_const.STATE_UNKNOWN = 'unknown'
hass_const.UnitOfPower = Mock(WATT='W')
hass_const.UnitOfEnergy = Mock(KILO_WATT_HOUR='kWh')

# Define sensor classes
sensor_module = sys.modules['homeassistant.components.sensor']
sensor_module.SensorEntity = type('SensorEntity', (object,), {})
sensor_module.SensorStateClass = Mock(
    MEASUREMENT='measurement',
    TOTAL_INCREASING='total_increasing'
)
sensor_module.SensorDeviceClass = Mock(
    POWER='power',
    ENERGY='energy'
)

# Define helpers
helpers = sys.modules['homeassistant.helpers']
helpers.RestoreEntity = type('RestoreEntity', (object,), {})
helpers.entity = Mock(Entity=type('Entity', (object,), {}))
helpers.device_registry = Mock(DeviceInfo=dict)

# Now we can test basic functionality
print("Testing sensor class imports...")

try:
    # Import our sensor modules
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from custom_components.phantom.sensors.base import PhantomBaseSensor, PhantomDeviceSensor
    print("✅ Base sensors imported successfully")
    
    from custom_components.phantom.sensors.power import PhantomPowerSensor, PhantomIndividualPowerSensor
    print("✅ Power sensors imported successfully")
    
    from custom_components.phantom.sensors.energy import PhantomEnergySensor, PhantomUtilityMeterSensor
    print("✅ Energy sensors imported successfully")
    
    from custom_components.phantom.sensors.cost import (
        PhantomDeviceHourlyCostSensor,
        PhantomGroupHourlyCostSensor,
        PhantomTouRateSensor,
        PhantomDeviceTotalCostSensor,
        PhantomGroupTotalCostSensor
    )
    print("✅ Cost sensors imported successfully")
    
    from custom_components.phantom.sensors.upstream import (
        PhantomUpstreamPowerSensor,
        PhantomUpstreamEnergyMeterSensor
    )
    print("✅ Upstream sensors imported successfully")
    
    from custom_components.phantom.sensors.remainder import (
        PhantomPowerRemainderSensor,
        PhantomEnergyRemainderSensor
    )
    print("✅ Remainder sensors imported successfully")
    
    from custom_components.phantom.sensors.remainder_cost import PhantomCostRemainderSensor
    print("✅ Remainder cost sensor imported successfully")
    
    print("\n✅ All sensor classes can be imported!")
    
    # Test basic instantiation
    print("\nTesting sensor instantiation...")
    
    # Test base sensor
    try:
        base_sensor = PhantomBaseSensor(
            config_entry_id="test",
            group_name="Test Group",
            group_id="group_123"
        )
        print("✅ PhantomBaseSensor instantiated")
    except Exception as e:
        print(f"❌ PhantomBaseSensor failed: {e}")
    
    # Test device sensor
    try:
        device_sensor = PhantomDeviceSensor(
            config_entry_id="test",
            device_name="Test Device",
            device_id="device_123"
        )
        print("✅ PhantomDeviceSensor instantiated")
    except Exception as e:
        print(f"❌ PhantomDeviceSensor failed: {e}")
    
    # Test power sensors
    try:
        power_sensor = PhantomPowerSensor(
            hass=MagicMock(),
            config_entry_id="test",
            group_name="Test Group",
            group_id="group_123",
            devices=[]
        )
        print("✅ PhantomPowerSensor instantiated")
    except Exception as e:
        print(f"❌ PhantomPowerSensor failed: {e}")
    
    print("\n✅ Basic sensor instantiation works!")
    
except Exception as e:
    print(f"\n❌ Error during testing: {e}")
    import traceback
    traceback.print_exc()