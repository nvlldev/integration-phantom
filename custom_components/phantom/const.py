"""Constants for the Phantom Power Monitoring integration."""

DOMAIN = "phantom"

CONF_DEVICES = "devices"
CONF_UPSTREAM_POWER_ENTITY = "upstream_power_entity"
CONF_UPSTREAM_ENERGY_ENTITY = "upstream_energy_entity"

# Legacy constants for backward compatibility
CONF_POWER_ENTITIES = "power_entities"
CONF_ENERGY_ENTITIES = "energy_entities"

ATTR_ENTITIES = "entities"
ATTR_UPSTREAM_POWER_ENTITY = "upstream_power_entity"
ATTR_UPSTREAM_ENERGY_ENTITY = "upstream_energy_entity"
ATTR_REMAINDER = "remainder"

DEVICE_CLASS_POWER = "power"
DEVICE_CLASS_ENERGY = "energy"

STATE_CLASS_MEASUREMENT = "measurement"
STATE_CLASS_TOTAL = "total"
STATE_CLASS_TOTAL_INCREASING = "total_increasing"

UNIT_WATT = "W"
UNIT_WATT_HOUR = "Wh"
UNIT_KILOWATT_HOUR = "kWh"