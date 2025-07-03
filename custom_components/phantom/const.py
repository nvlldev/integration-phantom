"""Constants for the Phantom Power Monitoring integration."""

DOMAIN = "phantom"

# Configuration constants
CONF_DEVICES = "devices"
CONF_UPSTREAM_POWER_ENTITY = "upstream_power_entity"
CONF_UPSTREAM_ENERGY_ENTITY = "upstream_energy_entity"
CONF_GROUPS = "groups"
CONF_GROUP_NAME = "name"
CONF_GROUP_ID = "id"
CONF_DEVICE_ID = "id"

# Tariff configuration constants
CONF_TARIFF = "tariff"
CONF_TARIFF_ENABLED = "enabled"
CONF_TARIFF_CURRENCY = "currency"
CONF_TARIFF_CURRENCY_SYMBOL = "currency_symbol"
CONF_TARIFF_RATE_STRUCTURE = "rate_structure"
CONF_TARIFF_RATE_TYPE = "type"
CONF_TARIFF_FLAT_RATE = "flat_rate"
CONF_TARIFF_TOU_RATES = "tou_rates"
CONF_TOU_NAME = "name"
CONF_TOU_RATE = "rate"
CONF_TOU_START_TIME = "start_time"
CONF_TOU_END_TIME = "end_time"
CONF_TOU_DAYS = "days"

# Tariff rate types
TARIFF_TYPE_FLAT = "flat"
TARIFF_TYPE_TOU = "tou"

# TOU period names
TOU_OFF_PEAK = "off_peak"
TOU_SHOULDER = "shoulder"
TOU_PEAK = "peak"

# External tariff sensor configuration
CONF_TARIFF_RATE_ENTITY = "rate_entity"
CONF_TARIFF_PERIOD_ENTITY = "period_entity"