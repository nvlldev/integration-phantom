# Phantom Power Monitoring

A Home Assistant custom integration for comprehensive power and energy monitoring with grouping, remainder calculation, and utility meter functionality.

## Features

### Power Monitoring
- **Individual Power Sensors**: Track power consumption for each selected device
- **Power Group Total**: Sum of all selected power entities
- **Power Remainder**: Calculate upstream power minus group total
- **Upstream Power**: Track the upstream/parent power entity

### Energy Monitoring
- **Individual Energy Meters**: Utility meters starting at 0 for each energy entity
- **Energy Group Total**: Sum of all selected energy entities (raw values)
- **Energy Remainder**: Calculate upstream energy meter minus group energy meters
- **Upstream Energy Meter**: Utility meter for upstream energy starting at 0

### Smart Features
- **Automatic Unit Conversion**: Converts Wh to kWh automatically
- **Reset Detection**: Handles meter resets gracefully
- **Percentage Calculations**: Shows what % of group/upstream each entity represents
- **State Restoration**: Maintains values through Home Assistant restarts
- **Partial Availability**: Sensors remain available even if some source entities are unavailable

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Install"
7. Restart Home Assistant

### Manual Installation
1. Copy the `phantom` folder to your `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Phantom Power Monitoring"

## Configuration

### Step 1: Select Entities
Choose which power and/or energy entities you want to monitor:
- **Power Entities**: Select sensors with device class "power" (Watts)
- **Energy Entities**: Select sensors with device class "energy" (kWh/Wh)

### Step 2: Configure Upstream Entities (Optional)
If you want remainder calculations, select upstream entities:
- **Upstream Power Entity**: The parent/source power entity
- **Upstream Energy Entity**: The parent/source energy entity

## Created Sensors

When you configure power entities, you get:
- `[Device Name] power` - Individual power sensor for each device
- `Power` - Total power of all selected devices
- `Upstream power` - Upstream power entity (if configured)
- `Power remainder` - Upstream power minus group total (if configured)

When you configure energy entities, you get:
- `[Device Name] meter` - Individual utility meter starting at 0 for each device
- `Energy` - Total energy of all selected devices (raw values)
- `Upstream energy meter` - Upstream utility meter starting at 0 (if configured)
- `Energy remainder` - Upstream energy meter minus group energy meters (if configured)

## Sensor Attributes

### Individual Power/Energy Sensors
- `percent_of_group`: Percentage of the group total this entity represents
- `percent_of_upstream`: Percentage of the upstream total this entity represents (if configured)
- `source_entity`: Original entity ID being tracked

### Utility Meters
- `baseline`: The starting value when the meter was created
- `source_entity`: Original entity ID being tracked

## Examples

### Basic Power Monitoring
Monitor kitchen appliances:
- Microwave: 800W
- Dishwasher: 1200W
- **Power total**: 2000W
- **Microwave percentage**: 40% of group

### Energy Tracking with Remainder
Track bedroom devices with main bedroom circuit:
- Bedroom Lights: 2.5 kWh (since setup)
- Bedroom Fan: 1.2 kWh (since setup)
- Main Bedroom Circuit: 5.0 kWh (since setup)
- **Energy remainder**: 1.3 kWh (other devices on the circuit)

### Unit Conversion
The integration automatically handles different units:
- Source in Wh → Displayed as kWh
- Source in kWh → Displayed as kWh

## Use Cases

### Home Energy Management
- Track which devices consume the most power
- Monitor energy usage patterns over time
- Identify phantom loads and standby consumption
- Calculate energy costs per device

### Circuit Monitoring
- Monitor branch circuits vs main circuits
- Identify unaccounted energy usage
- Balance loads across circuits
- Detect electrical issues

### Solar/Battery Systems
- Track consumption vs production
- Monitor battery charging/discharging
- Calculate net energy usage
- Optimize energy usage patterns

## Troubleshooting

### Sensors Showing "Unavailable"
1. **Check Source Entities**: Ensure all selected entities exist and have valid states
2. **Entity ID Format**: Verify entity IDs are in format `domain.entity_name`
3. **Device Classes**: Ensure entities have correct device classes (power/energy)
4. **Units**: Check that energy entities use kWh or Wh units

### Remainder Sensors Always Unavailable
- **Power Remainder**: Requires both group entities AND upstream entity to be available
- **Energy Remainder**: Requires both utility meters AND upstream meter to be available
- Check that upstream entities are configured correctly

### Incorrect Values
1. **Unit Conversion**: Energy values in Wh are automatically converted to kWh
2. **Baseline Issues**: Utility meters start at 0 when created, not from source value
3. **Reset Detection**: Large decreases in source values trigger reset handling

### Debug Logging
Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: info
  logs:
    custom_components.phantom: debug
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Ask questions and share ideas in GitHub Discussions
- **Documentation**: Check the Home Assistant Community Forum

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

### v1.0.0 (Latest)
- Initial release
- Power and energy monitoring with grouping
- Remainder calculations using utility meters
- Automatic unit conversion (Wh → kWh)
- Percentage calculations
- Individual device tracking
- State restoration and reset detection