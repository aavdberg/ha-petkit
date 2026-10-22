# Troubleshooting & Debugging Guide

This guide helps resolve common issues with the **ha-petkit** integration and explains how to gather detailed diagnostic logs for support.

---

## Common Issues & Solutions

### 1. Device entities show as `Unavailable`
- **Cause**: The BLE connection timed out or signal strength is too weak.
- **Solution**:
  - Check signal strength via `sensor.<device>_rssi`. An RSSI weaker than `-85 dBm` indicates marginal connection.
  - Install an [ESPHome Bluetooth Proxy](setup.md#step-3-optimizing-range-with-esphome-bluetooth-proxies) closer to the fountain.
  - Verify the fountain is plugged in and turned on.

### 2. Controls (e.g. Mode / Power Switch) are ignored by device
- **Cause**: Authentication verification (CMD 86) failed or the session timed out.
- **Solution**:
  - On a normal connection, the integration reads device info (CMD 213), verifies the stored secret (CMD 86), and syncs the time (CMD 84). CMD 73 registers a secret only during initial setup or re-pairing. If another client (such as the official Petkit smartphone app) connects to the fountain over BLE at the same time, it can disconnect or reset the fountain's auth session.
  - Ensure the official Petkit smartphone app is closed or Bluetooth on your phone is toggled off while Home Assistant is managing the device.

### 3. Filter percentage is incorrect after changing filter
- **Solution**:
  - Press the `button.<device>_reset_filter` entity in Home Assistant to send CMD 222 and reset filter life to 100%.

---

## Enabling Debug Logs

When reporting an issue, debug logs are essential for tracing BLE GATT commands and response payloads.

Add the following configuration to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.petkit_ble: debug
```

Or enable debug logging directly from the UI:
1. Go to **Settings** → **Devices & Services** → **Petkit BLE**.
2. Click **Enable debug logging** in the left menu.
3. Reproduce the problem (or wait 2-3 polling cycles).
4. Click **Disable debug logging** to download the log file.

---

## Reporting Issues with Action Timelines

When opening a bug report on GitHub:
1. Attach your sanitized debug log file.
2. Provide a **Timestamped Action Timeline** explaining what you did and at what time. For example:
   ```
   14:02:00 - Turned on debug logs
   14:02:15 - Toggled switch.fountain_power to OFF in HA dashboard
   14:02:30 - Fountain LED stayed on, HA entity reverted to ON
   ```
   This allows developers to locate the exact BLE command frame in the logs.
