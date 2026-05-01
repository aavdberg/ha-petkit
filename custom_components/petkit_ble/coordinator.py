"""DataUpdateCoordinator for Petkit BLE."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    async_ble_device_from_address,
    async_last_service_info,
    async_register_callback,
    async_scanner_count,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .ble_client import PetkitBleClient, PetkitFountainData
from .const import CONF_ADDRESS, CONF_DEVICE_SECRET, CONF_MODEL, CONF_NAME, DOMAIN, KNOWN_ALIASES, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

# How long to wait for a connectable advertisement before giving up. The proxy
# emits adverts every ~500ms, but it can be unavailable for a few seconds while
# it is mid-connect to another device. A 15s grace window covers that case
# without significantly delaying genuine "device powered off" failures.
CONNECTABLE_WAIT_TIMEOUT = 15.0


class PetkitBleCoordinator(DataUpdateCoordinator[PetkitFountainData]):
    """Coordinator that polls a Petkit fountain over BLE."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise the coordinator from a config entry."""
        self._address: str = config_entry.data[CONF_ADDRESS]
        self._alias: str = config_entry.data[CONF_MODEL]
        self._name: str = config_entry.data[CONF_NAME]
        self._config_entry = config_entry
        self._ble_lock = asyncio.Lock()

        # Stored secret from device initialization (may be None for legacy entries)
        secret_hex = config_entry.data.get(CONF_DEVICE_SECRET)
        try:
            self._secret: bytes | None = bytes.fromhex(secret_hex) if secret_hex else None
        except ValueError:
            _LOGGER.warning("Corrupted device secret for %s, treating as None", self._address)
            self._secret = None

        # Track drink events across polls
        self._prev_detect_status: int | None = None
        self._drink_event_count: int = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._address}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )

    def _log_unreachable_diagnostics(self) -> None:
        """Emit a single diagnostic log line explaining why the device is not connectable.

        Distinguishes between "no scanner has ever seen the device" (likely off
        or out of range) and "device is advertising but no connectable path is
        currently available" (proxy slot busy / non-connectable scanner only).
        """
        try:
            scanner_count_total = async_scanner_count(self.hass, connectable=False)
            scanner_count_conn = async_scanner_count(self.hass, connectable=True)
        except Exception:  # diagnostics must never raise
            scanner_count_total = scanner_count_conn = -1

        last_any = async_last_service_info(self.hass, self._address, connectable=False)
        last_conn = async_last_service_info(self.hass, self._address, connectable=True)

        if last_any is None:
            _LOGGER.warning(
                "%s (%s) is not advertising on any of %d scanner(s) "
                "(connectable scanners: %d). Device may be powered off or out of range.",
                self._name,
                self._address,
                scanner_count_total,
                scanner_count_conn,
            )
            return

        now = time.monotonic()
        age_any = now - last_any.time if last_any.time else 0.0

        if last_conn is None:
            _LOGGER.warning(
                "%s (%s) seen via %s (rssi=%s, %.1fs ago) but no connectable scanner "
                "currently has it (%d connectable / %d total scanners). "
                "Proxy slot may be busy or the advert was not connectable.",
                self._name,
                self._address,
                last_any.source,
                last_any.rssi,
                age_any,
                scanner_count_conn,
                scanner_count_total,
            )
        else:
            age_conn = now - last_conn.time if last_conn.time else 0.0
            _LOGGER.warning(
                "%s (%s) connectable advert seen via %s (rssi=%s, %.1fs ago) "
                "but async_ble_device_from_address returned None. "
                "Likely a transient HA bluetooth state.",
                self._name,
                self._address,
                last_conn.source,
                last_conn.rssi,
                age_conn,
            )

    async def _wait_for_connectable_device(self, timeout: float) -> BLEDevice | None:
        """Wait up to ``timeout`` seconds for a connectable advertisement.

        Returns the resolved BLEDevice, or None if no connectable advertisement
        is seen in time. Uses HA's bluetooth callback so we react as soon as a
        new advert arrives instead of polling.

        The callback is registered *before* the initial address lookup so we
        cannot miss an advertisement that arrives between the lookup and the
        registration.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()

        @callback
        def _on_advertisement(
            _service_info: BluetoothServiceInfoBleak,
            _change: BluetoothChange,
        ) -> None:
            if not future.done():
                future.set_result(None)

        cancel = async_register_callback(
            self.hass,
            _on_advertisement,
            {"address": self._address, "connectable": True},
            BluetoothScanningMode.PASSIVE,
        )
        try:
            # Re-check immediately after registration to close the race window
            # between the caller's initial lookup and our callback being live.
            device = async_ble_device_from_address(self.hass, self._address, connectable=True)
            if device is not None:
                return device

            try:
                await asyncio.wait_for(future, timeout)
            except TimeoutError:
                return None
        finally:
            cancel()

        return async_ble_device_from_address(self.hass, self._address, connectable=True)

    async def _get_ble_client(self) -> PetkitBleClient | None:
        """Resolve the device and return a client, waiting briefly if needed.

        Diagnostic warnings are only emitted on *final* failure, so transient
        proxy contention that resolves within the grace window stays silent.
        """
        device = async_ble_device_from_address(self.hass, self._address, connectable=True)
        if device is None:
            _LOGGER.debug(
                "%s (%s) not immediately connectable, waiting up to %.0fs for advertisement",
                self._name,
                self._address,
                CONNECTABLE_WAIT_TIMEOUT,
            )
            device = await self._wait_for_connectable_device(CONNECTABLE_WAIT_TIMEOUT)
        if device is None:
            self._log_unreachable_diagnostics()
            return None
        return PetkitBleClient(device)

    async def _async_update_data(self) -> PetkitFountainData:
        """Fetch the latest data from the fountain."""
        async with self._ble_lock:
            client = await self._get_ble_client()
            if client is None:
                raise UpdateFailed(f"Petkit fountain {self._name} ({self._address}) not reachable via Bluetooth")
            try:
                data = await client.async_poll(self._alias, self._secret)
            except Exception as exc:
                raise UpdateFailed(f"Error communicating with {self._name}: {exc}") from exc

        _LOGGER.debug(
            "Polled %s: power=%s mode=%s firmware=%s", self._name, data.power_status, data.mode, data.firmware
        )

        # Self-heal persistence: if the BLE client inferred a corrected alias
        # from the CMD 210 payload (e.g. when the original entry stored a MAC
        # as CONF_MODEL), persist the corrected alias to the config entry so
        # subsequent polls — and any switch/select writes — use the correct
        # device model immediately.
        if data.alias and data.alias != self._alias and data.alias in KNOWN_ALIASES:
            _LOGGER.warning(
                "Auto-correcting stored model for %s (%s): %r → %r. Persisting to config entry.",
                self._name,
                self._address,
                self._alias,
                data.alias,
            )
            self._alias = data.alias
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={**self._config_entry.data, CONF_MODEL: data.alias},
            )

        # Track drink events: detect_status transitions 0→1
        # No pump check — in smart mode the pump may be off while pet drinks
        cur_detect = data.detect_status
        if self._prev_detect_status is not None and self._prev_detect_status == 0 and cur_detect == 1:
            self._drink_event_count += 1
            _LOGGER.debug("Drink event detected (count=%d)", self._drink_event_count)
        self._prev_detect_status = cur_detect
        data.drink_event_count = self._drink_event_count

        # RSSI from the most recent BLE advertisement (no connection required)
        service_info = async_last_service_info(self.hass, self._address, connectable=False)
        if service_info is not None:
            data.rssi = service_info.rssi

        return data

    async def async_send_command(self, cmd: int, data: list[int]) -> bool:
        """Send a single BLE command, serialised with the poll lock.

        Returns True on success, False if the device was not reachable or the
        command failed.
        """
        async with self._ble_lock:
            client = await self._get_ble_client()
            if client is None:
                _LOGGER.warning(
                    "Cannot send CMD %d: %s (%s) not reachable via Bluetooth",
                    cmd,
                    self._name,
                    self._address,
                )
                return False
            return await client.async_send_command(cmd, data, self._alias, self._secret)
