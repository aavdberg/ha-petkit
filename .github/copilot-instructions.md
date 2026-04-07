# GitHub Copilot Instructions — ha-petkit

This file provides persistent context for GitHub Copilot so it understands the project
without needing to re-learn the codebase on every session.

---

## Project Overview

**ha-petkit** is a Home Assistant custom integration that connects to Petkit water fountains
locally via Bluetooth Low Energy (BLE). It uses Home Assistant's native Bluetooth stack,
supporting both local adapters and ESPHome Bluetooth proxies transparently.

- **Repo**: https://github.com/aavdberg/ha-petkit
- **Domain**: `petkit_ble`
- **HA minimum version**: 2024.1
- **Python target**: 3.12
- **Linter**: ruff (configured in `pyproject.toml`)

---

## Repository Structure

```
custom_components/petkit_ble/
├── __init__.py          # Integration setup/unload; uses entry.runtime_data pattern
├── manifest.json        # BLE matchers, dependencies, version
├── const.py             # All constants: UUIDs, command IDs, aliases, flow rates, epoch offset
├── ble_client.py        # Full BLE protocol: auth, frame encode/decode, CMD parsing
├── coordinator.py       # DataUpdateCoordinator; 60s poll via async_ble_device_from_address()
├── config_flow.py       # async_step_bluetooth() (auto) + async_step_user() (manual/scan)
├── entity.py            # Base PetkitBleEntity(CoordinatorEntity) with DeviceInfo
├── sensor.py            # 10 sensors (filter %, pump runtime, water, energy, battery, RSSI, …)
├── binary_sensor.py     # 8 binary sensors (pump running, warnings, DND, pet, AC, low battery)
├── button.py            # Reset filter (CMD 222), pump on/off (CMD 220)
├── switch.py            # Power switch (CMD 220)
├── strings.json         # Source-of-truth translation strings (English)
└── translations/
    ├── en.json          # English
    ├── nl.json          # Dutch
    └── uk.json          # Ukrainian

.github/
├── workflows/
│   ├── lint.yml         # Ruff lint + format check + HACS validation (on push/PR to main & dev)
│   ├── copilot-review.yml  # Copilot auto code review on PRs to main & dev
│   ├── pre-release.yml  # Auto pre-release tag on every push to dev (for HACS beta testing)
│   └── release.yml      # Auto GitHub Release on merge to main (based on manifest version)
└── copilot-instructions.md  # THIS FILE — update when protocol/devices/architecture changes
```

---

## BLE Protocol

### GATT Characteristics
- **Write UUID**: `0000aaa2-0000-1000-8000-00805f9b34fb` (write-without-response)
- **Notify UUID**: `0000aaa1-0000-1000-8000-00805f9b34fb`

### Frame Format
```
[0xFA, 0xFC, 0xFD, cmd, type, seq, data_len, 0x00, ...payload..., 0xFB]
```

### Authentication Sequence (every connection)
1. **CMD 213** — request device ID
2. **CMD 73** — request challenge bytes
3. **CMD 86** — send computed secret; response[0] must equal `1` for success
4. **CMD 84** — set device time (Petkit epoch: 2000-01-01, offset = 946684800)

### CTW3 Authentication Quirk (CRITICAL)
Always use `[0]*6` as the `device_id` for secret computation, **regardless** of what
CMD 213 returns. Using the actual CMD 213 bytes causes CMD 86 to fail and the device
disconnects silently.

### Secret Computation
```python
base = list(reversed([0]*6))          # always [0,0,0,0,0,0]
if base[-2] == 0 and base[-1] == 0:
    base[-2], base[-1] = 13, 37
secret = [0] * (8 - len(base)) + base  # left-pad to 8 bytes
```

### Key Commands
| CMD | Direction | Purpose |
|-----|-----------|---------|
| 213 | Read | Device ID |
| 73  | Read | Challenge bytes |
| 86  | Write | Auth secret |
| 84  | Write | Set device time |
| 210 | Read | Device state (W4/W5/CTW2) |
| 211 | Read | Device state (CTW3) |
| 66  | Read | Firmware version |
| 220 | Write | Power on/off |
| 222 | Write | Reset filter |

### State Payload Layout
- **W4/W5/CTW2** (CMD 210): 12+ bytes, big-endian
- **CTW3** (CMD 211): 26+ bytes — has `suspend_status`, `electric_status`, `battery_level`, `detect_status`

---

## Calculated Sensor Values

### Filter Days Remaining
```python
if mode == 1:
    days = ceil(filter_pct / 100 * 60)
elif mode == 2:
    days = ceil((filter_pct / 100 * 30) * (on + off) / on)
```

### Water Purified Today (liters)
```python
divisor = {CTW3: 3.0, W5C: 1.0, W4X: 1.8}.get(alias, 2.0)
liters = (flow_rate_lpm * pump_runtime_today_min / 60) / divisor
```

### Energy Today (kWh)
```python
power_w = 0.182 if alias == W5C else 0.75
kwh = power_w * pump_runtime_min / 60 / 1000
```

---

## HA Integration Patterns Used

- **`async_ble_device_from_address(hass, address, connectable=True)`** — transparently
  routes BLE connections through ESPHome Bluetooth proxies; no special proxy handling needed.
- **`DataUpdateCoordinator`** — 60-second polling interval; raises `UpdateFailed` on errors.
- **`entry.runtime_data`** — stores the coordinator instance (modern HA pattern, HA 2024.1+).
- **`async_step_bluetooth()`** — triggered automatically by HA when a matching BLE device
  is seen (matchers defined in `manifest.json` under the `bluetooth` key).
- **`CoordinatorEntity`** — all platform entities inherit from `PetkitBleEntity`.

---

## Device Alias Detection (from BLE Name)

Order matters — check more specific aliases first:
```
W4XUVC → W4X UVC
W4X    → W4X
W5C    → W5C
W5N    → W5N
W5     → W5
CTW3   → CTW3
CTW2   → CTW2
```

---

## Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Production — HACS users install from here; auto GitHub Release on merge |
| `dev` | Development & testing — all features merge here first |
| `feature/*` | Individual features — PR to `dev` |
| `fix/*` | Bug fixes — PR to `dev` |
| `chore/*` | Non-code changes (docs, CI, deps) — PR to `dev` |

Both `main` and `dev` are protected: PRs required, ruff lint must pass.

### ⚠️ CRITICAL RULE — Always follow this workflow:
```
git checkout dev && git pull
git checkout -b fix/my-fix          # or feature/, chore/
# make changes
git add ... && git commit -m "fix: ..."
git push -u origin fix/my-fix
gh pr create --base dev --head fix/my-fix --title "..." --body "..."
# wait for CI to pass, then merge
```

**NEVER commit or push directly to `dev` or `main`.**  
Even as admin (bypassed protection), direct pushes skip CI and break the audit trail.
Every change — no matter how small — must go through a PR to `dev`.

---

## Code Conventions

- **Language**: All code comments, docstrings, commit messages, and documentation in **English**.
- **Python**: 3.12+, type hints required, `from __future__ import annotations` in every module.
- **Imports**: Use `from collections.abc import Callable` (not `from typing import Callable`).
- **Linter**: ruff — run `ruff check custom_components/` before committing.
- **Commit style**: Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`).
- **Translations**: Add keys to `strings.json` first, then mirror to all `translations/*.json`.
- **New sensors**: Add to `sensor.py` description list + `strings.json` + all translation files.
- **No direct push to `main` or `dev`** — always use a PR.

---

## Known Issues / Quirks

- CTW3 always uses `[0]*6` as device_id in auth — see `ble_client.py` L270-283.
- HACS brands asset (`custom_components/petkit_ble/brand/icon.png`) not yet provided;
  currently relies on fallback check in brands repository.
- Cloud coordinator not yet implemented — only local BLE supported.
- ruff `UP035`: always import `Callable` from `collections.abc`, not `typing`.
