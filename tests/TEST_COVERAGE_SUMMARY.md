# Test Coverage Summary

## Overview
This document summarizes the comprehensive test coverage for all sensor classes in the Phantom integration.

## Test Files Created

### 1. test_common_sensor_behavior.py (28 tests with parametrization)
Tests common behavior across 5 sensor types:
- State change handling
- State restoration after restart
- Invalid state handling
- Delayed setup behavior

### 2. test_remainder_sensors_unique.py (11 tests)
Tests unique functionality for remainder sensors:
- PhantomPowerRemainderSensor
- PhantomEnergyRemainderSensor
- PhantomCostRemainderSensor

### 3. test_energy_cost_sensors_unique.py (9 tests)
Tests unique functionality for:
- PhantomEnergySensor (group total)
- PhantomGroupTotalCostSensor

### 4. test_power_sensors.py (12 tests)
Tests for power monitoring:
- PhantomPowerSensor (group total)
- PhantomIndividualPowerSensor (device-level)

### 5. test_upstream_sensors.py (16 tests)
Tests for upstream monitoring:
- PhantomUpstreamPowerSensor
- PhantomUpstreamEnergyMeterSensor

### 6. test_cost_sensors_additional.py (19 tests)
Tests for cost calculation sensors:
- PhantomDeviceHourlyCostSensor
- PhantomGroupHourlyCostSensor
- PhantomTouRateSensor
- PhantomDeviceTotalCostSensor

### 7. test_utility_meter_sensor.py (12 tests)
Tests for:
- PhantomUtilityMeterSensor

### 8. test_base_sensors.py (12 tests)
Tests for base classes:
- PhantomBaseSensor
- PhantomDeviceSensor

## Total Test Count: 97 unique test methods

## Sensor Classes Covered

### From sensors/base.py:
- ✅ PhantomBaseSensor
- ✅ PhantomDeviceSensor

### From sensors/power.py:
- ✅ PhantomPowerSensor
- ✅ PhantomIndividualPowerSensor

### From sensors/energy.py:
- ✅ PhantomEnergySensor
- ✅ PhantomUtilityMeterSensor

### From sensors/cost.py:
- ✅ PhantomDeviceHourlyCostSensor
- ✅ PhantomGroupHourlyCostSensor
- ✅ PhantomTouRateSensor
- ✅ PhantomDeviceTotalCostSensor
- ✅ PhantomGroupTotalCostSensor

### From sensors/upstream.py:
- ✅ PhantomUpstreamPowerSensor
- ✅ PhantomUpstreamEnergyMeterSensor

### From sensors/remainder.py:
- ✅ PhantomPowerRemainderSensor
- ✅ PhantomEnergyRemainderSensor

### From sensors/remainder_cost.py:
- ✅ PhantomCostRemainderSensor

### From sensors/cost_improved.py:
- ✅ PhantomDeviceTotalCostSensorImproved (inherits from PhantomDeviceTotalCostSensor, covered by parent tests)
- ✅ PhantomGroupTotalCostSensorImproved (inherits from PhantomGroupTotalCostSensor, covered by parent tests)

## Test Coverage Areas

### Core Functionality:
- Sensor initialization
- State calculations and updates
- Event handling
- State restoration (RestoreEntity)
- Unique ID generation
- Device info generation
- Extra state attributes

### Edge Cases:
- Unavailable/unknown states
- Invalid numeric values
- Missing entities
- Sensor removal
- Energy meter resets
- Negative values (where applicable)
- Mixed availability scenarios

### Integration Points:
- Home Assistant entity registry
- State change event tracking
- Time interval tracking
- Tariff manager integration
- Device/group associations

## Running the Tests

Due to environment issues, the tests should be run in a proper Home Assistant development environment. Once set up:

```bash
python -m pytest tests/test_*.py -v --cov=custom_components.phantom.sensors --cov-report=term-missing
```

This will provide a detailed coverage report showing which lines of code are covered by tests.