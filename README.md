# Reiri Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/swhebell/reiri_ha)

This integration allows for local control of Reiri Home air conditioners via Home Assistant.

## How it Works

The integration establishes a persistent WebSocket connection to the Reiri controller on the local network. It polls for state updates and sends commands which the controller translates to the underlying DIII-Net protocol used by the AC units. This allows for direct control without relying on cloud services.

## Key Features

*   **Local Control**: Communicates directly with the controller; no internet connection required.
*   **Auto-Discovery**: Automatically detects connected AC units.
*   **Optimistic State Updates**: The Reiri hardware can be slow to acknowledge commands (latency >60s). This integration updates the Home Assistant UI immediately upon user action to effectively manage this latency.
*   **Fan & Mode Control**: Supports standard operating modes and unit-specific fan speeds.
*   **Tested Hardware**: Verified on a **Daikin VRV** setup. Compatibility with other models is not guaranteed.

## Installation

### HACS (Recommended)

1.  Add `https://github.com/swhebell/reiri_ha` as a Custom Repository in HACS.
2.  Download and restart Home Assistant.

### Manual

1.  Copy the `custom_components/reiri` folder to your `config/custom_components/` directory.
2.  Restart Home Assistant.

## Configuration

Add the integration via **Settings > Devices & Services** by searching for **Reiri**.

Required information:
*   **IP Address**: The local IP address of the Reiri hub.
*   **Credentials**: Reiri username and password.

## Known Limitations

**State Update Latency**: Due to hardware limitations, the Reiri controller may take time to report state changes. This integration latches the reported state in Home Assistant for 60 seconds after a command is sent to prevent the UI from temporarily reverting to the previous state.

## Alternatives

If this integration does not meet your requirements, the following alternatives for controlling Daikin VRV/VRF systems exist (note: these have not been tested or verified):

*   **Modbus via DCPA01**: The Daikin DCPA01 is an official DIII-Net to Modbus RTU adapter. It may be possible to interface with this adapter using a Modbus USB stick or Ethernet gateway.
*   **Direct DIII-Net Connection**: The underlying F1/F2 bus protocol is proprietary. Community projects (e.g., P1P2Serial) exist that attempt to reverse-engineer this protocol, though this approach requires custom hardware and carries higher implementation complexity.

## License

MIT. See [LICENSE](LICENSE) for details.
