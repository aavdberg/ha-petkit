# Petkit BLE — Home Assistant Integration

[![Lint](https://github.com/aavdberg/ha-petkit/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/aavdberg/ha-petkit/actions/workflows/lint.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Local Bluetooth integration for **Petkit water fountains** (W4, W5, CTW3 series).  
Communicates directly over BLE — no cloud, no API token, no Petkit account required.

## Supported Devices

| Model     | BLE Name       | Notes                          |
|-----------|---------------|-------------------------------|
| CTW3      | Petkit_CTW3*  | Battery + AC, extra sensors   |
| CTW2      | Petkit_CTW2   |                               |
| W5C       | Petkit_W5C    |                               |
| W5N       | Petkit_W5N    |                               |
| W5        | Petkit_W5     |                               |
| W4X UVC   | Petkit_W4XUVC |                               |
| W4X       | Petkit_W4X    |                               |

## Features

- **Sensors**: filter life %, pump runtime, water purified, energy today, filter days remaining, battery (CTW3), RSSI
- **Binary sensors**: pump running, water missing, filter warning, hardware failure, DND, pet detected (CTW3), AC power (CTW3), low battery (CTW3)
- **Buttons**: reset filter, pump on, pump off
- **Switch**: power on/off
- **ESPHome Bluetooth proxy support** — works transparently via Home Assistant's native Bluetooth stack

## Requirements

- Home Assistant 2024.1 or newer
- A Bluetooth adapter or [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)

## Installation via HACS

1. In HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/aavdberg/ha-petkit` with category **Integration**
3. Install **Petkit BLE** and restart Home Assistant

## Testing the Dev Branch

> **Note:** HACS 2.x no longer supports branch selection in the UI. Use one of the methods below to test the `dev` branch.

### Option A — Manual copy (quickest)

1. In Home Assistant, open **File Editor** or connect via **SSH / Samba**
2. Copy the folder `custom_components/petkit_ble` from the `dev` branch to:
   ```
   /config/custom_components/petkit_ble/
   ```
3. Restart Home Assistant

To download the dev branch as a zip:
```
https://github.com/aavdberg/ha-petkit/archive/refs/heads/dev.zip
```
Extract and copy the `custom_components/petkit_ble` folder.

### Option B — HACS beta release (recommended for ongoing testing)

Every push to `dev` automatically creates a **pre-release** tag (e.g. `v1.0.0-dev.202604071200`).

1. In HACS, open the **Petkit BLE** repository
2. Select the **⋮ menu → Show details**
3. Enable **"Show beta releases"** in your HACS settings (⋮ → Settings → Experimental)
4. The latest dev pre-release will appear as an available update in HACS

### Option C — Git clone via SSH

```bash
cd /config/custom_components
git clone -b dev https://github.com/aavdberg/ha-petkit.git petkit_ble_dev
# Then symlink or copy the inner folder:
cp -r petkit_ble_dev/custom_components/petkit_ble ./petkit_ble
```


## Configuration

After installation, go to **Settings → Devices & Services → Add Integration → Petkit BLE**.

HA will scan for nearby Petkit fountains automatically. If none appear, enter the device's Bluetooth MAC address manually (found in the Petkit app or your router's ARP table).

The integration polls the fountain every 60 seconds. Commands (pump on/off, filter reset) connect on demand and refresh the state immediately after.

## Dashboard

A ready-made dashboard YAML is included in [`docs/dashboard.yaml`](docs/dashboard.yaml) that mirrors the Petkit iOS app layout.

### Import the dashboard

1. In Home Assistant, go to **Settings → Dashboards → Add Dashboard**
2. Choose **New dashboard from scratch**
3. Open the new dashboard, click ⋮ → **Edit dashboard** → ⋮ → **Raw configuration editor**
4. Paste the contents of [`docs/dashboard.yaml`](docs/dashboard.yaml)
5. Save

> **Note:** The YAML uses entity prefix `petkit_ctw3_100`. If your device has a different prefix, use find-and-replace to update all entity IDs.

### Sections

| Section | Contents |
|---------|----------|
| **Controls** | Power switch, mode selector (Normal/Smart) |
| **Status** | Pump running, pet drinking, AC power, DND, warnings |
| **Daily Statistics** | Water purified, energy used, pump runtime, drink events |
| **Filter** | Filter life gauge, days remaining, reset button |
| **Battery** | Battery gauge, voltage, AC power, pump suspended |
| **Settings** | Smart work/sleep timing, LED brightness & schedule, DND schedule |
| **Device Info** | Firmware, hardware version, BLE RSSI, total pump runtime, UVC |

---

## Protocol Notes

Communication uses a proprietary BLE protocol over two GATT characteristics (notify + write-without-response). Authentication is required on every connection.

---

## Development

### Branching Strategy

```
feature/* or fix/*
        │
        ▼  Pull Request + lint check
       dev         ← development & testing
        │
        ▼  Pull Request + lint check
      main         ← production (HACS users)
                      → automatic GitHub Release
```

| Branch | Purpose | Protected |
|---|---|---|
| `main` | Stable production release | ✅ PR required + lint must pass |
| `dev` | Integration & testing | ✅ PR required + lint must pass |
| `feature/*` | New functionality | Free — PR to `dev` |
| `fix/*` | Bug fixes | Free — PR to `dev` |

### Contributing

1. Branch off `dev`:
   ```bash
   git checkout dev
   git checkout -b feature/my-feature
   ```
2. Commit your changes:
   ```bash
   git commit -m "feat: description of the change"
   ```
3. Push and open a **Pull Request to `dev`**:
   ```bash
   git push origin feature/my-feature
   ```
4. The lint check (ruff) and Copilot code review run automatically.
5. When `dev` is stable, a PR to `main` is opened to trigger a release.

### Releases

Every merge to `main` automatically creates a GitHub Release based on the `version` field in `manifest.json`.  
Bump the version in `manifest.json` on `dev` before opening a release PR.

### Local Development

```bash
# Install linter
pip install ruff

# Check for lint errors
ruff check custom_components/

# Check formatting
ruff format --check custom_components/

# Auto-fix issues
ruff check --fix custom_components/
```


