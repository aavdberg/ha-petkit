"""DataUpdateCoordinator for Petkit BLE."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .ble_client import PetkitBleClient, PetkitFountainData
from .const import CONF_ADDRESS, CONF_MODEL, CONF_NAME, DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class PetkitBleCoordinator(DataUpdateCoordinator[PetkitFountainData]):
    """Coordinator that polls a Petkit fountain over BLE."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise the coordinator from a config entry."""
        self._address: str = config_entry.data[CONF_ADDRESS]
        self._alias: str = config_entry.data[CONF_MODEL]
        self._name: str = config_entry.data[CONF_NAME]
        self._ble_lock = asyncio.Lock()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._address}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )

    def _get_ble_device(self) -> PetkitBleClient | None:
        """Return a BLE client for the fountain, or None if not reachable."""
        ble_device = async_ble_device_from_address(self.hass, self._address, connectable=True)
        if ble_device is None:
            return None
        return PetkitBleClient(ble_device)

    async def _async_update_data(self) -> PetkitFountainData:
        """Fetch the latest data from the fountain."""
        async with self._ble_lock:
            client = self._get_ble_device()
            if client is None:
                raise UpdateFailed(f"Petkit fountain {self._name} ({self._address}) not reachable via Bluetooth")
            try:
                data = await client.async_poll(self._alias)
            except Exception as exc:
                raise UpdateFailed(f"Error communicating with {self._name}: {exc}") from exc

        _LOGGER.debug("Polled %s: power=%s mode=%s", self._name, data.power_status, data.mode)
        return data

    async def async_send_command(self, cmd: int, data: list[int]) -> bool:
        """Send a single BLE command, serialised with the poll lock.

        Returns True on success, False if the device was not reachable or the
        command failed.
        """
        async with self._ble_lock:
            client = self._get_ble_device()
            if client is None:
                _LOGGER.warning(
                    "Cannot send CMD %d: %s (%s) not reachable via Bluetooth",
                    cmd,
                    self._name,
                    self._address,
                )
                return False
            return await client.async_send_command(cmd, data, self._alias)
