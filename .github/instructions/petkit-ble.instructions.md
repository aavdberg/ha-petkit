---
applyTo: "custom_components/petkit_ble/**"
---

# ha-petkit BLE Integration — Copilot Skill

Specialized context for the `petkit_ble` Home Assistant custom integration.
Apply this knowledge when reading, writing, or reviewing code in `custom_components/petkit_ble/`.

## Project Essentials

- **Domain:** `petkit_ble`
- **Protocol:** Bluetooth Low Energy (BLE), Petkit proprietary framing
- **HA minimum:** 2024.1 — uses `entry.runtime_data`, `CoordinatorEntity`, `async_ble_device_from_address`
- **Python:** 3.12+, `from __future__ import annotations` in every module, `collections.abc.Callable`
- **Linter:** ruff — run `uv run ruff check custom_components/` before committing
- **Language:** ALL code, comments, docstrings, commit messages, PR titles/descriptions, and GitHub issues MUST be written in English. No exceptions, even when the user writes in another language.
- **Branching:** feature/* and fix/* → PR to `dev`; never push directly to `dev` or `main`

## BLE Frame Format

```
[FA FC FD, cmd, type, seq, len_lo, 0x00, ...payload..., FB]
```

- `FRAME_TYPE_SEND = 0x01` for requests
- All const values (UUIDs, CMD IDs) live in `const.py`

## Authentication Sequence

1. **First connection** (no stored secret): CMD 213 → CMD 73 (device_id_be + random_secret) → CMD 86 (secret) → CMD 84 (time)
2. **Subsequent connections**: CMD 86 (stored secret) → CMD 84 (time)
3. Secret persisted in `entry.data["device_secret"]` (hex string)
4. `client.used_secret` is set after successful auth; coordinator detects first-time init and saves

## Device Aliases & Detection

```
W4XUVC → W4X UVC   (check more-specific first)
W4X    → W4X
W5C    → W5C
W5N    → W5N
W5     → W5
CTW3   → CTW3
CTW2   → CTW2
```

`CTW3_ALIASES` constant holds the set of CTW3 variant names.

## Key Commands

| CMD | Constant | Direction | Notes |
|-----|----------|-----------|-------|
| 213 | `CMD_GET_DEVICE_INFO` | Read | Device ID + serial; empty payload |
| 73  | `CMD_AUTH_INIT` | Write | 16 bytes: device_id_be(8) + secret(8) |
| 86  | `CMD_AUTH_VERIFY` | Write | 8 bytes secret; response[0]==1 = success |
| 84  | `CMD_SET_TIME` | Write | Petkit epoch offset = 946684800 (2000-01-01) |
| 200 | `CMD_GET_FIRMWARE` | Read | payload[0]=hardware_version, payload[1]=firmware |
| 210 | `CMD_GET_STATE` | Read | Device state (all models) |
| 211 | `CMD_GET_CONFIG` | Read | Settings — **NOT sent to CTW3** (device never responds) |
| 66  | `CMD_GET_BATTERY` | Read | Battery voltage (non-CTW3) |
| 220 | `CMD_SET_MODE` | Write | [mode, 0]: 0=off, 1=normal, 2=smart |
| 222 | `CMD_RESET_FILTER` | Write | Empty payload; resets filter % to 100 |

## State Payload Layouts

**CMD 210 generic (W4/W5/CTW2) — 12+ bytes (big-endian):**
```
[0] powerStatus  [1] mode  [2] dnd  [3] warningBreakdown  [4] warningWaterMissing
[5] warningFilter  [6-9] pumpRuntime(uint32)  [10] filterPercent  [11] runningStatus
[12-15] pumpRuntimeToday(uint32, optional)  [16] smartTimeOn  [17] smartTimeOff
```

**CMD 210 CTW3 — 26+ bytes (big-endian):**
```
[0] powerStatus  [1] suspendStatus  [2] mode  [3] electricStatus  [4] dndState
[5] warningBreakdown  [6] warningWaterMissing  [7] lowBattery  [8] warningFilter
[9-12] pumpRuntime(uint32)  [13] filterPercent  [14] runningStatus
[15-18] pumpRuntimeToday(uint32)  [19] detectStatus
[20-21] supplyVoltageMv(int16)  [22-23] batteryVoltageMv(int16)
[24] batteryPercent  [25] moduleStatus
```

## CTW3 Quirks

- **CMD 211 is skipped** — CTW3 never responds; skipping saves 5s per poll
- **CMD 230 (0xe6) unsolicited push** — CTW3 sends extended state pushes at any time; `_send_and_wait` discards mismatched cmd bytes via `asyncio.Queue`
- **Auth uses `device_id_be` from CMD 213** — do NOT use `[0]*8` for CTW3 anymore (PR #17 fixed this)

## Calculated Properties (on `PetkitFountainData`)

- `filter_days_remaining` — depends on `mode`, `smart_time_on/off`, `filter_percent`
- `water_purified_today_liters` — uses `FLOW_RATE_LPM` and `FLOW_DIVISOR` from `const.py`
- `energy_today_kwh` — uses `POWER_COEFF_W` from `const.py`

## Adding a New Sensor

1. Add field to `PetkitFountainData` in `ble_client.py`
2. Parse in the correct `_parse_state_*` or `_parse_config_*` method
3. Add `PetkitSensorEntityDescription` entry to `SENSOR_DESCRIPTIONS` in `sensor.py`
4. Add translation key to `strings.json` (source of truth)
5. Mirror to `translations/en.json`, `translations/nl.json`, `translations/uk.json`

## File Map

```
ble_client.py    — BLE protocol, frame encode/decode, auth, state parsers, PetkitFountainData
coordinator.py   — DataUpdateCoordinator (60s), secret load/save, RSSI
config_flow.py   — bluetooth auto-discovery + manual entry
entity.py        — PetkitBleEntity base (CoordinatorEntity + DeviceInfo)
sensor.py        — 10 diagnostic + measurement sensors
binary_sensor.py — 9 binary sensors (pump, warnings, DND, pet, AC, battery)
button.py        — reset filter, pump on/off
switch.py        — power on/off
select.py        — mode selection (normal/smart)
const.py         — all constants: UUIDs, CMD IDs, aliases, flow rates, epoch offset
strings.json     — source-of-truth translations (English)
```
