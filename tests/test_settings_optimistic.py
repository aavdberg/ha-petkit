"""Tests for the CMD 211/221 settings flow.

Covers:
- The `config_loaded` flag is False on a fresh PetkitFountainData and only
  flips to True after a CMD 211 parser has run.
- `build_full_settings_payload` logs a one-shot warning when called against
  data that has never had CMD 211 parsed (firmware that never replies to
  CMD 211, e.g. CTW3 fw 111 in production logs).

The optimistic local-state update performed by the switch/number/time
platforms is exercised by reading the platform source and is not unit
tested here because the platforms depend on the Home Assistant stubs.
"""

from __future__ import annotations

import logging

from custom_components.petkit_ble.ble_client import (
    PetkitBleClient,
    PetkitFountainData,
)
from custom_components.petkit_ble.const import ALIAS_CTW3
from custom_components.petkit_ble.protocol import (
    _WARNED_NO_CONFIG,
    build_full_settings_payload,
)


class TestConfigLoadedFlag:
    """The config_loaded flag is the source of truth for 'CMD 211 has worked at least once'."""

    def test_default_is_false(self) -> None:
        """Fresh data has not seen CMD 211 yet."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        assert data.config_loaded is False

    def test_ctw3_parser_sets_flag(self) -> None:
        """Parsing a valid CTW3 settings payload sets the flag."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        # CTW3 settings layout (10 bytes):
        # [smart_work, smart_sleep, batt_work_hi, batt_work_lo,
        #  batt_sleep_hi, batt_sleep_lo, led_switch, led_brightness,
        #  dnd_enabled, child_lock]
        payload = bytes([10, 15, 0, 60, 0, 30, 1, 5, 0, 0])
        PetkitBleClient._parse_config_ctw3(data, payload)
        assert data.config_loaded is True
        assert data.smart_time_on == 10
        assert data.smart_time_off == 15
        assert data.led_switch == 1
        assert data.led_brightness == 5

    def test_ctw3_parser_short_payload_does_not_set_flag(self) -> None:
        """A truncated payload should not flip the flag — parser bails early."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        PetkitBleClient._parse_config_ctw3(data, b"\x00\x00")
        assert data.config_loaded is False

    def test_generic_parser_sets_flag(self) -> None:
        """W5/CTW2 parser also flips the flag."""
        data = PetkitFountainData(alias="W5")
        # generic settings layout: 14 bytes
        payload = bytes([5, 10, 1, 3, 0, 60, 0, 120, 0, 0, 0, 0, 0, 0])
        PetkitBleClient._parse_config_generic(data, payload)
        assert data.config_loaded is True
        assert data.led_switch == 1
        assert data.led_brightness == 3


class TestBuildFullSettingsPayloadWarning:
    """The CMD 221 builder warns once when CMD 211 has never replied."""

    def test_warns_when_config_not_loaded(self, caplog) -> None:
        """First call against unloaded data emits a WARNING."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        _WARNED_NO_CONFIG.discard(id(data))
        with caplog.at_level(logging.WARNING, logger="custom_components.petkit_ble.protocol"):
            build_full_settings_payload(data, led_switch=1)
        assert any("CMD 211" in r.message for r in caplog.records)

    def test_warns_only_once_per_data(self, caplog) -> None:
        """Second call against the same data does not re-warn."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        _WARNED_NO_CONFIG.discard(id(data))
        build_full_settings_payload(data, led_switch=1)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="custom_components.petkit_ble.protocol"):
            build_full_settings_payload(data, led_switch=0)
        assert not any("CMD 211" in r.message for r in caplog.records)

    def test_no_warning_when_config_loaded(self, caplog) -> None:
        """When CMD 211 has succeeded, no warning."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        data.config_loaded = True
        _WARNED_NO_CONFIG.discard(id(data))
        with caplog.at_level(logging.WARNING, logger="custom_components.petkit_ble.protocol"):
            build_full_settings_payload(data, led_switch=1)
        assert not any("CMD 211" in r.message for r in caplog.records)

    def test_payload_is_still_built(self) -> None:
        """The warning is non-fatal: the payload is still produced."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        _WARNED_NO_CONFIG.discard(id(data))
        payload = build_full_settings_payload(data, led_switch=1)
        # CTW3 layout, 10 bytes, led_switch at index 6.
        assert len(payload) == 10
        assert payload[6] == 1
