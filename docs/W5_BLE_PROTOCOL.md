# Petkit W5 / CTW2 BLE Protocol

> **Source:** This document is reproduced from
> [`mr-ransel/petkit-ble-reverse-engineering`](https://github.com/mr-ransel/petkit-ble-reverse-engineering/blob/main/W5_BLE_PROTOCOL.md)
> by [@mr-ransel](https://github.com/mr-ransel), used here for reference.
> All reverse-engineering credit goes to the original author.
>
> **ha-petkit notes** are appended at the bottom with findings from our own
> CTW3 log analysis and implementation experience.

---

# PetKit Eversweet Solo 2 (W5/CTW2) BLE Protocol

Reverse-engineered BLE protocol for the PetKit Eversweet Solo 2 wireless water fountain.

**Target device:** PetKit Eversweet Solo 2 (wireless water fountain)
**BLE advertisement name:** `Petkit_CTW2`

## Device Family

This protocol is shared across the W5 device family:

| BLE Name | Product | typeCode |
|---|---|---|
| `Petkit_W5` | Eversweet (original) | 1 |
| `Petkit_W5C` | Eversweet variant | 2 |
| `Petkit_W5N` | Eversweet variant | 3 |
| `Petkit_W4X` | Eversweet W4X | — |
| `Petkit_W4XUVC` | Eversweet W4X UVC | — |
| `Petkit_CTW2` | Eversweet Solo 2 (wireless) | — |

All use the same GATT service, packet framing, and command set. Minor differences exist in extended features based on `typeCode` and firmware version.

## GATT Service

| UUID | Role |
|---|---|
| `0000aaa0-0000-1000-8000-00805f9b34fb` | Service |
| `0000aaa2-0000-1000-8000-00805f9b34fb` | Write characteristic (commands to device) |
| `0000aaa1-0000-1000-8000-00805f9b34fb` | Notify characteristic (responses from device) |

## Packet Framing

All BLE packets (both directions) use the same framing:

```
FA FC FD <cmd:1> <type:1> <seq:1> <len_lo:1> <len_hi:1> [data:N] FB
```

| Field | Size | Description |
|---|---|---|
| Header | 3 bytes | Always `FA FC FD` |
| cmd | 1 byte | Command ID |
| type | 1 byte | 1=Request, 2=Response, 3=Non-response request |
| seq | 1 byte | Sequence number (0-255, wrapping) |
| len | 2 bytes | Little-endian payload length |
| data | N bytes | Payload (may be 0 bytes) |
| Trailer | 1 byte | Always `FB` |

## Connection & Authentication Flow

### Normal (read-only, uninitialized device)

1. **Connect** to GATT service
2. **Subscribe** to notify characteristic (`0xAAA1`)
3. **CMD 213** — Get device ID + serial number
4. **CMD 86** — Verify with zero secret (8 null bytes). Works when deviceId == 0 (uninitialized)
5. **CMD 84** — Time sync (required before reads)
6. Read commands: CMD 200, CMD 210, CMD 211, CMD 66, CMD 215/216

### Full initialization flow (as done by the official app)

1. CMD 213 — Get device ID
2. If deviceId == 0 (new device): app calls a cloud API to get a server-assigned deviceId + secret
3. CMD 73 — Init device (writes deviceId + secret permanently to device)
4. CMD 86 — Verify with the assigned secret
5. CMD 84 — Time sync
6. Read/write commands

### Security model

- **Uninitialized devices (deviceId == 0)** accept a zero secret (8 null bytes) for CMD 86. This is the key discovery that enables cloud-free BLE access.
- **Initialized devices** require the exact 8-byte secret that was written during CMD 73. The secret is generated server-side.
- CMD 86 response: `data[0] == 1` means success, anything else means failure. On failure, the device may disconnect.
- Sending commands before authentication causes the device to disconnect.

## Command Reference

### Authentication & Setup Commands

#### CMD 213 — Get Device ID
- **Direction:** Request → Response
- **Request payload:** (empty)
- **Response payload:** 8 bytes deviceId (little-endian) + up to 14 bytes ASCII serial number

#### CMD 86 — Verify Secret
- **Direction:** Request → Response
- **Request payload:** 8 bytes (secret, zero-padded)
- **Response payload:** 1 byte — `0x01` = success, `0x00` = failure

#### CMD 73 — Initialize Device (WRITES PERMANENTLY)
- **Direction:** Request → Response
- **Request payload:** 8 bytes deviceId (big-endian) + 8 bytes secret
- **Response payload:** 1 byte — `0x01` = success
- **WARNING:** This permanently writes the device ID and secret. Can only be undone with a physical factory reset.

#### CMD 84 — Time Sync
- **Direction:** Request → Response
- **Request payload:** 1 byte (0x00) + 4 bytes seconds since 2000-01-01 (big-endian signed int) + 1 byte timezone (UTC offset + 12)
- **Response payload:** 1 byte — `0x01` = success

### Read Commands

#### CMD 210 — Get Running State
- **Direction:** Request → Response
- **Request payload:** (empty)
- **Response payload (12-16 bytes):**

| Byte | Field | Values |
|---|---|---|
| 0 | powerStatus | 0=off, 1=on |
| 1 | mode | 0=off, 1=normal, 2=smart |
| 2 | nightNoDisturb | 0/1 |
| 3 | breakdownWarning | 0/1 |
| 4 | **lackWarning** | **0=OK, 1=LOW WATER** |
| 5 | filterWarning | 0/1 |
| 6-9 | pumpRunTime | 4 bytes big-endian, total seconds |
| 10 | filterPercent | 0-100, filter life remaining % |
| 11 | runStatus | 0=idle, 1=running |
| 12-15 | todayPumpRunTime | (optional) 4 bytes big-endian, seconds today |

The `todayPumpRunTime` field (bytes 12-15) is only present on newer firmware versions:
- typeCode 2: firmware >= 24
- Other typeCodes: firmware >= 35

#### CMD 211 — Get Settings
- **Direction:** Request → Response
- **Request payload:** (empty)
- **Response payload (13-14 bytes):**

| Byte | Field | Type |
|---|---|---|
| 0 | smartWorkingTime | Minutes (smart mode run duration) |
| 1 | smartSleepTime | Minutes (smart mode sleep duration) |
| 2 | lampRingSwitch | 0=off, 1=on |
| 3 | lampRingBrightness | 0-255 |
| 4-5 | lampRingLightUpTime | Big-endian, minutes from midnight |
| 6-7 | lampRingGoOutTime | Big-endian, minutes from midnight |
| 8 | noDisturbingSwitch | 0=off, 1=on |
| 9-10 | noDisturbingStartTime | Big-endian, minutes from midnight |
| 11-12 | noDisturbingEndTime | Big-endian, minutes from midnight |
| 13 | isLock | (optional) 0/1, child lock |

The `isLock` byte is only present on firmware versions that support it.

#### CMD 200 — Get Hardware/Firmware Version
- **Direction:** Request → Response
- **Request payload:** (empty)
- **Response payload:** 2+ bytes — `[hardware_version, firmware_version, ...]`
  - Byte 0: hardware revision (integer, e.g. `1`)
  - Byte 1: firmware version (integer, e.g. `111`)
  - Additional bytes may be present on some models (CTW3 returns 17 bytes)

#### CMD 66 — Get Battery/Voltage
- **Direction:** Request → Response
- **Request payload:** (empty)
- **Response payload:** 2 bytes — little-endian raw voltage value
- **Note:** This is a raw ADC value, not a calibrated percentage. Not a reliable water level indicator.

#### CMD 215 — Get Extended Light Settings
- **Direction:** Request → Response
- **Request payload:** (empty)
- **Response payload:**

| Byte | Field |
|---|---|
| 0 | lightConfig (1=config mode 1, else mode 2) |
| 1 | number of time slots |
| 2-5 | reserved (0) |
| 6+ | Time slots: 5 bytes each (2B start_minutes_BE, 2B end_minutes_BE, 1B reserved) |

#### CMD 216 — Get Extended DND Settings
- Same structure as CMD 215 but for Do Not Disturb schedules
- `disturbConfig` instead of `lightConfig`

### Write Commands

#### CMD 220 — Change Device Mode
- **Request payload:** 2 bytes — `[mode, submode]`
- **Modes:** 0=off, 1=normal, 2=smart
- **Response:** `data[0] == 0` indicates failure

#### CMD 221 — Write All Settings
- **Request payload (13-14 bytes):**

| Byte | Field |
|---|---|
| 0 | smartWorkingTime |
| 1 | smartSleepTime |
| 2 | lampRingSwitch |
| 3 | lampRingBrightness |
| 4-5 | lampRingLightUpTime (big-endian) |
| 6-7 | lampRingGoOutTime (big-endian) |
| 8 | noDisturbingSwitch |
| 9-10 | noDisturbingStartTime (big-endian) |
| 11-12 | noDisturbingEndTime (big-endian) |
| 13 | isLock (if supported) |

#### CMD 222 — Reset Filter
- **Request payload:** (empty)
- Resets filter usage counter to 100%.

#### CMD 225 — Update Light Schedule (Extended)
- **Request payload:**

| Byte | Field |
|---|---|
| 0 | lightConfig (1 or 0) |
| 1 | number of time slots |
| 2-5 | reserved (0) |
| 6+ | Time slots: 5 bytes each (2B start, 2B end, 1B 0x00) |

#### CMD 226 — Update DND Schedule (Extended)
- Same structure as CMD 225 but for Do Not Disturb

#### CMD 83 — Start OTA
- **Request payload:** (empty)
- Puts device into OTA (firmware update) mode

#### CMD 230 — Device Push Notification (device-initiated)
- **Direction:** Device → Phone (unsolicited push)
- Contains combined state + settings data (25+ bytes)
- Client should respond with `CMD 230, data=[0x01], type=RESPONSE` to acknowledge
- Layout varies by firmware version — older firmware uses 25 bytes (12 state + 13 settings), newer firmware inserts 4 bytes of `todayPumpRunTime` between state and settings (29 bytes total)

---

## ha-petkit Implementation Notes

These notes are specific to the `ha-petkit` integration and supplement the protocol
documentation above with findings from real device log analysis.

### CTW3 Differences

The CTW3 (Eversweet 3 Pro) uses **CMD 211** (state) instead of CMD 210, with a 26+ byte payload:

| Byte | Field |
|---|---|
| 0 | powerStatus |
| 1 | suspendStatus |
| 2 | mode |
| 3 | electricStatus |
| 4 | dndState |
| 5 | warningBreakdown |
| 6 | warningWaterMissing |
| 7 | lowBattery |
| 8 | warningFilter |
| 9-12 | pumpRunTime (big-endian uint32, seconds) |
| 13 | filterPercent |
| 14 | runningStatus |
| 15-18 | pumpRuntimeToday (big-endian uint32, seconds) |
| 19 | detectStatus |
| 20-21 | supplyVoltageMv (big-endian int16) |
| 22-23 | batteryVoltageMv (big-endian int16) |
| 24 | batteryPercent |
| 25 | moduleStatus |

**CTW3 does NOT respond to CMD 211 (get settings).** The device sends unsolicited
CMD 230 (0xe6) extended state push notifications but never replies to CMD 211 requests.
ha-petkit skips CMD 211 for CTW3 to avoid a 5-second timeout per poll.

### Authentication (ha-petkit approach)

ha-petkit uses a **self-init** strategy with a random 8-byte secret:

1. **First connection** (no stored secret):
   - CMD 213 — fetch device ID
   - CMD 73 — init with `device_id_be + random_8_byte_secret`
   - CMD 86 — verify with `random_8_byte_secret`
   - CMD 84 — set time
   - Secret is saved to the HA config entry for subsequent connections.

2. **Subsequent connections** (stored secret):
   - CMD 86 — verify directly with stored secret
   - CMD 84 — set time
   - CMD 213 and CMD 73 are skipped.

### CMD 200 — Hardware / Firmware Version Parsing

CTW3 returns 17 bytes from CMD 200. Only bytes 0 and 1 are used:
- `payload[0]` → `hardware_version` (e.g. `1`)
- `payload[1]` → `firmware` (e.g. `111`)

### Unsolicited Notifications

The CTW3 sends CMD 230 (0xe6) push notifications at irregular intervals. These must
not be mistaken for responses to CMD 210 or CMD 211 requests. ha-petkit validates the
`cmd` byte of every received frame and discards mismatches.
