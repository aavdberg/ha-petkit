"""DataUpdateCoordinator for Petkit BLE."""

from __future__ import annotations

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

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._address}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )

    async def _async_update_data(self) -> PetkitFountainData:
        """Fetch the latest data from the fountain."""
        ble_device = async_ble_device_from_address(self.hass, self._address, connectable=True)
        if ble_device is None:
            raise UpdateFailed(f"Petkit fountain {self._name} ({self._address}) not reachable via Bluetooth")

        client = PetkitBleClient(ble_device)
        try:
            data = await client.async_poll(self._alias)
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with {self._name}: {exc}") from exc

        _LOGGER.debug("Polled %s: power=%s mode=%s", self._name, data.power_status, data.mode)
        return data
