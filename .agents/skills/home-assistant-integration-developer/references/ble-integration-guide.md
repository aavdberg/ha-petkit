# BLE Integration Guide

## Overview

Home Assistant provides a native Bluetooth stack that supports both local adapters and
ESPHome Bluetooth proxies transparently. Use `async_ble_device_from_address()` to get
a connectable BLE device — HA handles routing through the best available adapter.

## GATT Characteristics

Define UUIDs as constants:

```python
WRITE_CHAR_UUID = "0000aaa2-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000aaa1-0000-1000-8000-00805f9b34fb"
```

## Connection Pattern

```python
from homeassistant.components.bluetooth import async_ble_device_from_address

async def async_connect(self) -> None:
    """Connect to device."""
    ble_device = async_ble_device_from_address(
        self.hass, self._address, connectable=True
    )
    if ble_device is None:
        raise DeviceUnavailable("Device not found")

    self._client = BleakClient(ble_device)
    await self._client.connect()
    await self._client.start_notify(NOTIFY_CHAR_UUID, self._notification_handler)
```

## ESPHome Proxies

**No special handling needed.** The `async_ble_device_from_address()` function
transparently routes through ESPHome Bluetooth proxies. If the device is reachable
via a proxy, HA will use it automatically.

## Frame Format

Many BLE devices use a framing protocol:

```python
def encode_frame(cmd: int, seq: int, payload: bytes) -> bytes:
    """Encode a command frame."""
    data_len = len(payload)
    frame = bytearray([
        FRAME_START,     # e.g., 0xFA
        FRAME_HEADER_1,  # e.g., 0xFC
        FRAME_HEADER_2,  # e.g., 0xFD
        cmd,
        0x01,            # type
        seq,             # sequence number
        data_len,
        0x00,
        *payload,
        FRAME_END,       # e.g., 0xFB
    ])
    return bytes(frame)
```

## Authentication

Some devices require authentication per-connection:

1. Request a challenge from the device
2. Compute a response (often using a shared secret)
3. Send the response; verify acknowledgment
4. Optionally sync device time

**Store the secret** in `config_entry.data`, not in code:

```python
secret = entry.data.get(CONF_SECRET)
if secret:
    await client.authenticate(bytes.fromhex(secret))
```

## Send and Wait Pattern

For request-response protocols, use an `asyncio.Event`:

```python
async def _send_and_wait(self, cmd: int, payload: bytes) -> bytes | None:
    """Send command and wait for response."""
    self._response_event.clear()
    self._expected_cmd = cmd
    await self._client.write_gatt_char(WRITE_CHAR_UUID, frame)

    try:
        await asyncio.wait_for(self._response_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        return None

    return self._response_data
```

**Important:** Verify the response command matches the request to avoid
processing unsolicited notifications as responses.

## BLE-Specific Anti-Patterns

| Anti-pattern | Correct approach |
|---|---|
| Holding BLE connection open between polls | Connect, poll, disconnect (saves battery) |
| Concurrent GATT operations | Use `asyncio.Lock()` for serial access |
| Ignoring `BleakError` subtypes | Handle `BleakDeviceNotFoundError`, `BleakDBusError` |
| Large payload without MTU check | Negotiate MTU or fragment writes |
| Using actual device ID for auth when it should be zeroed | Check protocol docs — some devices require fixed auth bytes |
