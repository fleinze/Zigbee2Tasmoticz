# Zigbee2Tasmoticz

Zigbee2Tasmoticz is a Domoticz plugin designed to integrate Zigbee devices managed by [Zigbee2Tasmota](https://tasmota.github.io/docs/Zigbee/) into the Domoticz home automation system. This plugin is a fork of the original [Tasmoticz](https://github.com/foba-1/Tasmoticz) plugin, tailored specifically for Zigbee2Tasmota integration.

## Features

- **Seamless Integration**: Connect and control Zigbee devices through Domoticz using Zigbee2Tasmota as the bridge.
- **Real-time Monitoring**: Receive immediate updates from Zigbee devices within the Domoticz interface.
- **Device Compatibility**: Supports a wide range of Zigbee devices compatible with Zigbee2Tasmota.

## Prerequisites

Before installing the plugin, ensure you have:

- [Domoticz](https://www.domoticz.com/) installed on your system.
- A Zigbee coordinator device running [Zigbee2Tasmota](https://tasmota.github.io/docs/Zigbee/).
- [Python 3](https://www.python.org/downloads/) installed on your system.

## Installation

1. **Clone the Repository**:

   Navigate to your Domoticz plugins directory:

   ```bash
   cd domoticz/plugins
   ```

   Clone the Zigbee2Tasmoticz repository:

   ```bash
   git clone https://github.com/fleinze/Zigbee2Tasmoticz.git
   ```

2. **Enable the Plugin in Domoticz**:

   - Restart the Domoticz service to recognize the new plugin.
   - Go to the Domoticz web interface.
   - Navigate to **Setup** > **Hardware**.
   - Add a new hardware device:
     - Select **Autodiscovery of Zigbee2Tasmota Devices** from the hardware type dropdown.
     - Configure the required settings (MQTT server details, tele and cmnd topics of the Zigbee2Tasmota-Gateway).
     - Click **Add** to enable the plugin.

## Configuration

After adding the plugin in Domoticz:

- **Device Discovery**: The plugin will automatically discover Zigbee devices managed by Zigbee2Tasmota. Discovered devices will appear under the **Devices** section in Domoticz.
- **Device Management**: Assign meaningful names and configure settings for each device as needed.

## Usage

Once configured:

- Control Zigbee devices directly from the Domoticz dashboard.
- Create automation scripts and events in Domoticz utilizing Zigbee device statuses and controls.

## Troubleshooting

- **Devices Not Appearing**: Ensure that your Zigbee coordinator is functioning correctly and that Zigbee2Tasmota is properly configured.
- **Connection Issues**: Verify that the MQTT broker details in the plugin configuration match those used by Zigbee2Tasmota.

For more detailed information on Zigbee2Tasmota, refer to the [official documentation](https://tasmota.github.io/docs/Zigbee/).

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
