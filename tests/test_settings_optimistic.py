"""Tests for the CMD 211/221 settings flow.

Covers:
- The ``config_loaded`` flag is False on a fresh PetkitFountainData and only
  flips to True after a CMD 211 parser has run.
- ``_reconcile_settings_into`` caches settings from a successful CMD 211 and
  re-applies them onto fresh data objects when CMD 211 fails to respond.
  This is the actual fix for the LED switch flip-back bug observed on CTW3
  firmware 111 (CMD 211 never replies).
- A one-shot WARNING is emitted on the first poll where CMD 211 fails AND
  the cache is still empty.
"""

from __future__ import annotations

import logging

import pytest

from custom_components.petkit_ble.ble_client import (
    PetkitBleClient,
    PetkitFountainData,
)
from custom_components.petkit_ble.const import ALIAS_CTW3
from custom_components.petkit_ble.coordinator import (
    _SETTINGS_FIELDS,
    _reconcile_settings_into,
)


class TestConfigLoadedFlag:
    """The config_loaded flag tracks 'CMD 211 has worked at least once'."""

    def test_default_is_false(self) -> None:
        data = PetkitFountainData(alias=ALIAS_CTW3)
        assert data.config_loaded is False

    def test_ctw3_parser_sets_flag(self) -> None:
        data = PetkitFountainData(alias=ALIAS_CTW3)
        # CTW3 settings layout (10 bytes):
        # [smart_work, smart_sleep, batt_work_hi, batt_work_lo,
        #  batt_sleep_hi, batt_sleep_lo, dnd_enabled, led_switch,
        #  led_brightness, child_lock]
        payload = bytes([10, 15, 0, 60, 0, 30, 0, 1, 5, 0])
        PetkitBleClient._parse_config_ctw3(data, payload)
        assert data.config_loaded is True
        assert data.led_switch == 1
        assert data.led_brightness == 5

    def test_ctw3_parser_short_payload_does_not_set_flag(self) -> None:
        data = PetkitFountainData(alias=ALIAS_CTW3)
        PetkitBleClient._parse_config_ctw3(data, b"\x00\x00")
        assert data.config_loaded is False

    def test_generic_parser_sets_flag(self) -> None:
        data = PetkitFountainData(alias="W5")
        payload = bytes([5, 10, 1, 3, 0, 60, 0, 120, 0, 0, 0, 0, 0, 0])
        PetkitBleClient._parse_config_generic(data, payload)
        assert data.config_loaded is True


class TestReconcileSettingsInto:
    """The coordinator preserves settings across polls when CMD 211 fails."""

    def test_successful_poll_populates_cache(self) -> None:
        cache: dict[str, int] = {}
        data = PetkitFountainData(alias=ALIAS_CTW3)
        data.config_loaded = True
        data.led_switch = 1
        data.led_brightness = 5
        data.smart_time_on = 10
        data.smart_time_off = 15
        data.battery_work_time = 60
        data.battery_sleep_time = 30

        warned = _reconcile_settings_into(data, cache, warned=False, name="x", address="y")

        assert warned is False
        assert cache["led_switch"] == 1
        assert cache["led_brightness"] == 5
        assert cache["smart_time_on"] == 10
        assert cache["battery_work_time"] == 60
        for field in _SETTINGS_FIELDS:
            assert field in cache

    def test_failed_poll_with_cache_restores_values(self) -> None:
        cache: dict[str, int] = {}
        # Step 1: a successful poll populates the cache.
        good = PetkitFountainData(alias=ALIAS_CTW3)
        good.config_loaded = True
        good.led_switch = 1
        good.led_brightness = 7
        good.smart_time_on = 20
        _reconcile_settings_into(good, cache, warned=False, name="x", address="y")

        # Step 2: a fresh data object simulating a poll where CMD 211 timed out.
        fresh = PetkitFountainData(alias=ALIAS_CTW3)
        assert fresh.config_loaded is False
        assert fresh.led_switch == 0  # dataclass default

        warned = _reconcile_settings_into(fresh, cache, warned=False, name="x", address="y")

        # Cached values must have been re-applied.
        assert fresh.led_switch == 1
        assert fresh.led_brightness == 7
        assert fresh.smart_time_on == 20
        # The data object is now treated as configured so subsequent CMD 221
        # writes do not zero out unrelated fields.
        assert fresh.config_loaded is True
        # The cache is non-empty so no warning is emitted.
        assert warned is False

    def test_failed_poll_without_cache_warns_once(self, caplog: pytest.LogCaptureFixture) -> None:
        cache: dict[str, int] = {}
        fresh = PetkitFountainData(alias=ALIAS_CTW3)

        with caplog.at_level(logging.WARNING, logger="custom_components.petkit_ble.coordinator"):
            warned = _reconcile_settings_into(fresh, cache, warned=False, name="x", address="y")
        assert warned is True
        assert any("CMD 211" in r.message for r in caplog.records)

        # Second failure with warned=True must NOT re-warn.
        caplog.clear()
        fresh2 = PetkitFountainData(alias=ALIAS_CTW3)
        with caplog.at_level(logging.WARNING, logger="custom_components.petkit_ble.coordinator"):
            warned = _reconcile_settings_into(fresh2, cache, warned=True, name="x", address="y")
        assert warned is True
        assert not any("CMD 211" in r.message for r in caplog.records)

    def test_user_write_into_cache_then_failed_poll_persists(self) -> None:
        """``apply_setting_optimistic`` writes into the cache; the next failed
        poll must restore the user-written value onto the fresh data object.

        This is the end-to-end contract for the LED-flip-back fix: even on
        firmware where CMD 211 never replies, a click on the LED switch
        results in ``led_switch`` being preserved across every subsequent
        coordinator refresh.
        """
        cache: dict[str, int] = {}
        # Simulate apply_setting_optimistic("led_switch", 1).
        cache["led_switch"] = 1

        fresh = PetkitFountainData(alias=ALIAS_CTW3)
        _reconcile_settings_into(fresh, cache, warned=False, name="x", address="y")
        assert fresh.led_switch == 1
        assert fresh.config_loaded is True
