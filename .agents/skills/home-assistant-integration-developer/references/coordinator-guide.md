# Coordinator Guide

## Setup Pattern

The coordinator fetches data and is the single source of truth:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

class MyCoordinator(DataUpdateCoordinator[MyDataClass]):
    """Coordinator for My Integration."""

    def __init__(self, hass: HomeAssistant, client: MyClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="My Integration",
            update_interval=timedelta(seconds=60),
        )
        self.client = client
        self._lock = asyncio.Lock()  # Serialize device access

    async def _async_update_data(self) -> MyDataClass:
        """Fetch data from device."""
        async with self._lock:
            try:
                return await self.client.async_get_data()
            except DeviceConnectionError as err:
                raise UpdateFailed(f"Error communicating: {err}") from err
```

## Runtime Data

**Use `entry.runtime_data`** (HA 2024.1+), not `hass.data[DOMAIN]`:

```python
# __init__.py
type MyConfigEntry = ConfigEntry[MyCoordinator]

async def async_setup_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Set up from config entry."""
    client = MyClient(entry.data[CONF_ADDRESS])
    coordinator = MyCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

Benefits over `hass.data`:
- Type-safe (generic ConfigEntry[T])
- Automatic cleanup on unload
- No manual dictionary management

## Error Handling

**Always** raise `UpdateFailed` from `_async_update_data()`:

```python
# ✅ Good
try:
    data = await self.client.fetch()
except ConnectionError as err:
    raise UpdateFailed(f"Connection failed: {err}") from err

# ❌ Bad — swallows the error
try:
    data = await self.client.fetch()
except Exception:
    return self._last_data  # Silently fails
```

For specific errors, preserve the chain with `from err`.

## Write Commands

For command-style operations (e.g., turn on/off), go through the coordinator:

```python
async def async_send_command(self, cmd: int, payload: bytes) -> None:
    """Send command to device."""
    async with self._lock:
        await self.client.send(cmd, payload)
    await self.async_request_refresh()  # Refresh state after command
```

Entities call: `await self.coordinator.async_send_command(CMD_POWER, payload)`

## Locking

Use `asyncio.Lock()` for any device that requires serial access:

```python
self._lock = asyncio.Lock()

async def _async_update_data(self):
    async with self._lock:
        # Only one operation at a time
        return await self.client.fetch()
```

This is critical for BLE devices which can only handle one GATT operation at a time.

## Resilient Data Handling

Always handle corrupted stored data gracefully:

```python
# ✅ Good
try:
    secret = bytes.fromhex(entry.data.get(CONF_SECRET, ""))
except ValueError:
    _LOGGER.warning("Invalid stored secret, re-initializing")
    secret = None
```
