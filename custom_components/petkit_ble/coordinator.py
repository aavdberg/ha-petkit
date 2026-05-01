"""DataUpdateCoordinator for Petkit BLE."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    async_ble_device_from_address,
    async_last_service_info,
    async_register_callback,
    async_scanner_count,
)
from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .ble_client import PetkitBleClient, PetkitFountainData
from .const import CONF_ADDRESS, CONF_DEVICE_SECRET, CONF_MODEL, CONF_NAME, DOMAIN, KNOWN_ALIASES, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Settings fields populated by CMD 211 and writable via CMD 221. When CMD 211
# fails (e.g. CTW3 firmware 111 never responds to it), these would otherwise
# stay at dataclass defaults and silently flip back after every poll, and any
# CMD 221 write would zero out unrelated fields. We cache the last known value
# of each on the coordinator and re-apply it onto fresh poll results so that
# user writes persist across polls even when the device never replies to 211.
_SETTINGS_FIELDS: tuple[str, ...] = (
    "smart_time_on",
    "smart_time_off",
    "led_switch",
    "led_brightness",
    "do_not_disturb_switch",
    "is_locked",
    "battery_work_time",
    "battery_sleep_time",
    "led_on_minutes",
    "led_off_minutes",
    "dnd_start_minutes",
    "dnd_end_minutes",
)

# How long to wait for a connectable advertisement before giving up. The proxy
# emits adverts every ~500ms, but it can be unavailable for a few seconds while
# it is mid-connect to another device. A 15s grace window covers that case
# without significantly delaying genuine "device powered off" failures.
CONNECTABLE_WAIT_TIMEOUT = 15.0


def _reconcile_settings_into(
    data: PetkitFountainData,
    cache: dict[str, int],
    *,
    warned: bool,
    name: str,
    address: str,
) -> bool:
    """Pure helper for ``PetkitBleCoordinator._reconcile_settings``.

    Mutates ``data`` and ``cache`` in place. Returns the new value of the
    ``warned_no_config`` flag (True once we've emitted the warning).

    Extracted as a free function so it can be unit-tested without
    constructing a full coordinator (which inherits from
    ``DataUpdateCoordinator`` and is awkward to instantiate).
    """
    if data.config_loaded:
        for field in _SETTINGS_FIELDS:
            cache[field] = getattr(data, field)
        return warned
    if cache:
        for field, value in cache.items():
            setattr(data, field, value)
        data.config_loaded = True
        return warned
    if not warned:
        _LOGGER.warning(
            "CMD 211 (read settings) has not yet succeeded for %s (%s, alias=%s); "
            "writing CMD 221 will use defaults for unread fields. The first "
            "successful poll or user-driven write will populate the cache.",
            name,
            address,
            data.alias,
        )
        return True
    return warned


@dataclass
class _DrinkCountState:
    """Mutable holder for the daily drink-event counter.

    Lives on the coordinator across polls. Extracted into a small
    dataclass so the counting and persistence logic can be unit-tested
    via free functions (``_track_drink_event_into`` /
    ``_load_drink_state_into``) without instantiating the full
    ``DataUpdateCoordinator`` chain (which is awkward to mock).
    """

    prev_detect_status: int | None = None
    count: int = 0
    date_iso: str = ""


async def _load_drink_state_into(state: _DrinkCountState, store: Any) -> None:
    """Populate ``state`` from a ``Store`` snapshot if one exists.

    Storage failures are swallowed at debug level — they must never block
    integration setup. A persisted count from a previous day is dropped so
    today's counter starts from zero.
    """
    try:
        stored = await store.async_load()
    except Exception as exc:
        _LOGGER.debug("Failed to load drink-count store: %s", exc)
        return
    if not stored:
        return
    try:
        state.count = int(stored.get("count", 0))
        state.date_iso = str(stored.get("date") or state.date_iso)
    except (TypeError, ValueError) as exc:
        _LOGGER.debug("Discarding corrupt drink-count store: %s", exc)
        return
    today_iso = date.today().isoformat()
    if state.date_iso != today_iso:
        state.count = 0
        state.date_iso = today_iso


async def _track_drink_event_into(
    state: _DrinkCountState,
    store: Any,
    data: PetkitFountainData,
) -> None:
    """Update ``state`` from a freshly polled ``data``; persist on change.

    Increments on a ``detect_status`` 0 → 1 transition. Resets the counter
    when the local date rolls over so the sensor is genuinely a per-day
    counter. Always writes the current count back onto ``data`` so the
    sensor reflects the latest value even when nothing changed.
    """
    today_iso = date.today().isoformat()
    if today_iso != state.date_iso:
        _LOGGER.debug(
            "Daily drink-count rollover %s → %s (was %d)",
            state.date_iso,
            today_iso,
            state.count,
        )
        state.date_iso = today_iso
        state.count = 0

    cur_detect = data.detect_status
    count_changed = False
    if state.prev_detect_status is not None and state.prev_detect_status == 0 and cur_detect == 1:
        state.count += 1
        count_changed = True
        _LOGGER.debug("Drink event detected (count=%d)", state.count)
    state.prev_detect_status = cur_detect
    data.drink_event_count = state.count

    if count_changed:
        try:
            await store.async_save({"count": state.count, "date": state.date_iso})
        except Exception as exc:
            _LOGGER.debug("Failed to persist drink-count store: %s", exc)


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

        # Track drink events across polls. The state is held in a small
        # dataclass so the counting + persistence logic can live in free
        # functions (testable without the full coordinator chain).
        self._drink_state = _DrinkCountState(date_iso=date.today().isoformat())
        self._drink_store: Store = Store(hass, version=1, key=f"{DOMAIN}_drink_count_{self._address.lower()}")

        # Cache for settings fields (CMD 211 / CMD 221). See _SETTINGS_FIELDS
        # docstring for rationale. Populated either by a successful CMD 211
        # parse or by an entity-driven write via apply_setting_optimistic().
        self._settings_cache: dict[str, int] = {}
        self._warned_no_config: bool = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._address}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )

    async def async_load_persistent_state(self) -> None:
        """Load the persisted drink-event counter from disk.

        Called once before the first refresh so a Home Assistant restart or
        integration reload no longer wipes today's count to zero.
        """
        await _load_drink_state_into(self._drink_state, self._drink_store)

    async def _track_drink_event(self, data: PetkitFountainData) -> None:
        """Thin wrapper around ``_track_drink_event_into`` for the poll loop."""
        await _track_drink_event_into(self._drink_state, self._drink_store, data)

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

        self._reconcile_settings(data)

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

        # Track drink events. Counter resets daily and persists across
        # restarts. See ``_track_drink_event`` for full rationale.
        await self._track_drink_event(data)

        # RSSI from the most recent BLE advertisement (no connection required)
        service_info = async_last_service_info(self.hass, self._address, connectable=False)
        if service_info is not None:
            data.rssi = service_info.rssi

        return data

    def _reconcile_settings(self, data: PetkitFountainData) -> None:
        """Reconcile the settings cache with a freshly polled data object.

        Each ``async_poll`` constructs a brand-new ``PetkitFountainData``, so
        any settings that were not refreshed by a CMD 211 response would
        revert to dataclass defaults — visibly flipping switches back in the
        UI and zeroing unrelated fields on the next CMD 221 write.
        """
        self._warned_no_config = _reconcile_settings_into(
            data,
            self._settings_cache,
            warned=self._warned_no_config,
            name=self._name,
            address=self._address,
        )

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

    @callback
    def apply_setting_optimistic(self, field: str, value: int) -> None:
        """Persist a CMD 221 write into the live data and the settings cache.

        Entities call this after a successful CMD 221 so that:
          1. The live ``coordinator.data`` reflects the new value immediately
             (so the UI does not flip back while waiting for the next poll).
          2. The cache survives the dataclass replacement performed by the
             next ``async_poll`` call. ``_async_update_data`` re-applies the
             cache when CMD 211 fails to populate the field naturally.

        ``async_set_updated_data`` is invoked so listeners (entities) refresh
        their state without waiting on a network round trip.
        """
        if field not in _SETTINGS_FIELDS:
            _LOGGER.debug("apply_setting_optimistic: unknown field %r ignored", field)
            return
        self._settings_cache[field] = value
        if self.data is not None:
            setattr(self.data, field, value)
            self.data.config_loaded = True
            self.async_set_updated_data(self.data)
