# Petkit BLE Integration Documentation & Wiki

Welcome to the documentation for **ha-petkit**, a Home Assistant custom integration that connects locally to Petkit smart water fountains via Bluetooth Low Energy (BLE).

---

## Documentation Sections

- [Supported Devices & Hardware Variants](supported-devices.md) — Product names, hardware revision codes (CTW3, CTW2, W5, W4X), advertisement names, and supported features per model.
- [Entity Reference & Calculations](entities.md) — Detailed description of all sensors, binary sensors, switches, buttons, numbers, and select entities, including mathematical formulas for filter life %, water purified, and energy consumption.
- [Installation & Setup](setup.md) — Step-by-step installation via HACS, Home Assistant Bluetooth auto-discovery, manual configuration, and configuring ESPHome Bluetooth Proxies.
- [Troubleshooting & Logs](troubleshooting.md) — Diagnosing BLE connection issues, understanding authentication sequences, and collecting debug logs with action timelines for bug reporting.
- [Automation Examples](automations.md) — Ready-to-use YAML automation examples for low water alerts, filter replacement reminders, and DND schedule synchronization.

---

## Overview & Architecture

The integration communicates directly with Petkit fountains over BLE without requiring a Petkit cloud account, internet connection, or external API key.

```
┌────────────────────────────────┐         Bluetooth (BLE)         ┌──────────────────────────┐
│                                │ ──────────────────────────────> │ Petkit Water Fountain    │
│  Home Assistant Core           │                                 │ (CTW3 / W5 / W4X / etc.) │
│  (DataUpdateCoordinator 60s)   │ <────────────────────────────── │                          │
│                                │   ESPHome BLE Proxy / Local     └──────────────────────────┘
└────────────────────────────────┘   Bluetooth Adapter
```

### Key Technical Characteristics
- **Local Control**: Direct GATT read/write operations over BLE (`0000aaa1` notify / `0000aaa2` write).
- **ESPHome Proxy Transparent Support**: Uses Home Assistant's `async_ble_device_from_address()` to work seamlessly over ESPHome Bluetooth proxies across your home.
- **Session Re-Authentication**: Implements per-connection authentication (CMD 213 → CMD 73 secret challenge → CMD 86 verification → CMD 84 time sync) to guarantee reliable state polling.
