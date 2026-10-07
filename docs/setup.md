# Installation & Setup Guide

This guide covers installing **ha-petkit** in Home Assistant, configuring Bluetooth integration, and optimizing BLE range using ESPHome Bluetooth Proxies.

---

## Requirements

- **Home Assistant**: Version 2024.1 or newer.
- **Bluetooth Hardware**: Either a local Bluetooth adapter on the Home Assistant host machine, or one or more [ESPHome Bluetooth Proxies](https://esphome.io/components/bluetooth_proxy.html) spread across your home.

---

## Step 1: Installation via HACS

### Installing Stable Releases (Recommended)
1. Open Home Assistant → **HACS** → **Integrations**.
2. Click the top-right menu (⋮) → **Custom repositories**.
3. Add Repository URL: `https://github.com/aavdberg/ha-petkit`
4. Category: **Integration**
5. Click **Add**, then search for **Petkit BLE** and click **Download**.
6. **Restart Home Assistant**.

### Testing Dev Beta Releases
If you want to test upcoming features before official release:
1. In HACS, open the **Petkit BLE** integration page.
2. Click **⋮ → Settings** or **Re-download**.
3. Enable **"Show beta releases"**.
4. Select the latest `vX.Y.Z-beta.N` pre-release and click **Download**.

---

## Step 2: Adding the Device in Home Assistant

### Option A: Automatic Discovery (Recommended)
When your Petkit fountain is powered on and within Bluetooth range:
1. Home Assistant will automatically show a notification: **"Discovered Petkit BLE"**.
2. Click **Configure** on the notification.
3. Confirm the discovered device name and submit.

### Option B: Manual Setup
If automatic discovery doesn't pop up:
1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Petkit BLE**.
3. Select your Petkit fountain from the list of nearby scanned Bluetooth devices.
4. Click **Submit**.

---

## Step 3: Optimizing Range with ESPHome Bluetooth Proxies

Petkit fountains communicate using low-power BLE. If your Home Assistant server is in a cabinet or far from the device, connection timeouts or missed updates may occur.

### Setting up an ESPHome BLE Proxy
Using an inexpensive ESP32 board (e.g. ESP32-WROOM / ESP32-C3) near your fountain eliminates distance issues:

```yaml
esphome:
  name: ble-proxy-livingroom

esp32:
  board: esp32dev
  framework:
    type: esp-idf

esp32_ble_tracker:
  scan_parameters:
    interval: 110ms
    window: 99ms
    active: true

bluetooth_proxy:
  active: true
```

> **How it works:** Home Assistant's native Bluetooth stack handles proxy routing automatically. **ha-petkit** uses `async_ble_device_from_address()`, so it automatically routes requests through whichever proxy or local adapter has the strongest signal to your Petkit fountain. No special configuration is required in the integration!
