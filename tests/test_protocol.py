"""Tests for the Petkit BLE protocol module."""

from __future__ import annotations

import struct
from unittest.mock import patch

from custom_components.petkit_ble.const import (
    FRAME_END,
    FRAME_HEADER,
    PETKIT_EPOCH_OFFSET,
)
from custom_components.petkit_ble.protocol import (
    build_change_mode_payload,
    build_ctw3_mode_payload,
    build_ctw3_select_mode_payload,
    build_init_payload,
    build_settings_payload_ctw3,
    build_settings_payload_generic,
    build_time_sync_payload,
)


class TestBuildTimeSyncPayload:
    """Tests for build_time_sync_payload."""

    def test_payload_length(self) -> None:
        """Payload must be exactly 6 bytes."""
        result = build_time_sync_payload()
        assert len(result) == 6

    def test_first_byte_zero(self) -> None:
        """First byte is always 0."""
        result = build_time_sync_payload()
        assert result[0] == 0

    def test_last_byte_thirteen(self) -> None:
        """Last byte is always 13."""
        result = build_time_sync_payload()
        assert result[5] == 13

    def test_seconds_encoding(self) -> None:
        """Middle 4 bytes encode seconds since Petkit epoch, big-endian."""
        fake_time = PETKIT_EPOCH_OFFSET + 0x01020304
        with patch("custom_components.petkit_ble.protocol.time") as mock_time:
            mock_time.time.return_value = fake_time
            result = build_time_sync_payload()
        assert result[1] == 0x01
        assert result[2] == 0x02
        assert result[3] == 0x03
        assert result[4] == 0x04


class TestBuildInitPayload:
    """Tests for build_init_payload."""

    def test_payload_length(self) -> None:
        """Payload must be 16 bytes (8 device_id + 8 secret)."""
        result = build_init_payload(0, bytes(8))
        assert len(result) == 16

    def test_device_id_encoding(self) -> None:
        """Device ID is packed big-endian as an unsigned 64-bit int."""
        result = build_init_payload(12345, b"\x01\x02\x03\x04\x05\x06\x07\x08")
        id_bytes = bytes(result[:8])
        device_id = struct.unpack(">Q", id_bytes)[0]
        assert device_id == 12345

    def test_secret_included(self) -> None:
        """Secret bytes appear in positions 8-15."""
        secret = b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22"
        result = build_init_payload(0, secret)
        assert bytes(result[8:16]) == secret

    def test_short_secret_padded(self) -> None:
        """A short secret is right-padded with zeros."""
        result = build_init_payload(0, b"\x01\x02\x03")
        assert bytes(result[8:16]) == b"\x01\x02\x03\x00\x00\x00\x00\x00"


class TestBuildSettingsPayloadGeneric:
    """Tests for build_settings_payload_generic."""

    def test_payload_length(self) -> None:
        """Generic settings payload is 14 bytes."""
        result = build_settings_payload_generic(5, 10)
        assert len(result) == 14

    def test_field_positions(self) -> None:
        """Verify each field is at the correct position."""
        result = build_settings_payload_generic(
            smart_work=5,
            smart_sleep=10,
            led_switch=1,
            led_brightness=7,
            led_on_minutes=480,  # 08:00
            led_off_minutes=1320,  # 22:00
            dnd_enabled=1,
            dnd_start_minutes=1380,  # 23:00
            dnd_end_minutes=420,  # 07:00
            child_lock=1,
        )
        assert result[0] == 5  # smart_work
        assert result[1] == 10  # smart_sleep
        assert result[2] == 1  # led_switch
        assert result[3] == 7  # led_brightness
        # led_on_minutes = 480 = 0x01E0
        assert result[4] == 0x01
        assert result[5] == 0xE0
        # led_off_minutes = 1320 = 0x0528
        assert result[6] == 0x05
        assert result[7] == 0x28
        assert result[8] == 1  # dnd_enabled
        # dnd_start = 1380 = 0x0564
        assert result[9] == 0x05
        assert result[10] == 0x64
        # dnd_end = 420 = 0x01A4
        assert result[11] == 0x01
        assert result[12] == 0xA4
        assert result[13] == 1  # child_lock


class TestBuildSettingsPayloadCTW3:
    """Tests for build_settings_payload_ctw3."""

    def test_payload_length(self) -> None:
        """CTW3 settings payload is 10 bytes."""
        result = build_settings_payload_ctw3(5, 10)
        assert len(result) == 10

    def test_field_positions(self) -> None:
        """Verify each field is at the correct position."""
        result = build_settings_payload_ctw3(
            smart_work=5,
            smart_sleep=10,
            battery_work_time=300,
            battery_sleep_time=600,
            led_switch=1,
            led_brightness=8,
            dnd_enabled=1,
            child_lock=1,
        )
        assert result[0] == 5
        assert result[1] == 10
        # battery_work_time = 300 = 0x012C
        assert result[2] == 0x01
        assert result[3] == 0x2C
        # battery_sleep_time = 600 = 0x0258
        assert result[4] == 0x02
        assert result[5] == 0x58
        assert result[6] == 1  # dnd_enabled
        assert result[7] == 1  # led_switch
        assert result[8] == 8  # led_brightness
        assert result[9] == 1  # child_lock

    def test_real_device_payload_decoding(self) -> None:
        """Regression: payloads captured from a real CTW3 (fw 111).

        The user toggled LED on, adjusted brightness, then toggled LED off
        between 18:52:13 and 18:52:48 in the 2026-05-03 debug log. After
        rotating the byte layout, the led_switch / led_brightness fields
        encoded by the integration must match the expected sequence.
        """
        cases = [
            # (led_switch, led_brightness, expected payload[6..9])
            (1, 1, [0, 1, 1, 0]),
            (0, 5, [0, 0, 5, 0]),
            (1, 8, [0, 1, 8, 0]),
            (1, 9, [0, 1, 9, 0]),
            (0, 8, [0, 0, 8, 0]),
        ]
        for led_switch, led_brightness, expected_tail in cases:
            payload = build_settings_payload_ctw3(
                smart_work=0,
                smart_sleep=0,
                led_switch=led_switch,
                led_brightness=led_brightness,
                dnd_enabled=0,
                child_lock=0,
            )
            assert payload[6:10] == expected_tail, (
                f"led_switch={led_switch}, brightness={led_brightness}: got {payload[6:10]}, expected {expected_tail}"
            )


class TestParseConfigCtw3:
    """Round-trip tests for _parse_config_ctw3.

    Real-device CMD 211 payloads are not available (CTW3 fw 111 never
    replies), so we synthesise payloads identical to what
    build_settings_payload_ctw3 emits and verify the parser populates the
    matching fields. This pins parser/builder symmetry.
    """

    def test_roundtrip_real_device_sequence(self) -> None:
        """Captured user actions (LED on -> brightness changes -> LED off)."""
        from custom_components.petkit_ble.ble_client import (
            PetkitBleClient,
            PetkitFountainData,
        )

        cases = [
            (1, 1),
            (0, 5),
            (1, 8),
            (1, 9),
            (0, 8),
        ]
        for led_switch, led_brightness in cases:
            payload = bytes(
                build_settings_payload_ctw3(
                    smart_work=0,
                    smart_sleep=0,
                    led_switch=led_switch,
                    led_brightness=led_brightness,
                    dnd_enabled=0,
                    child_lock=0,
                )
            )
            data = PetkitFountainData(alias="CTW3")
            PetkitBleClient._parse_config_ctw3(data, payload)
            assert data.led_switch == led_switch
            assert data.led_brightness == led_brightness
            assert data.do_not_disturb_switch == 0
            assert data.is_locked == 0

    def test_roundtrip_with_dnd_and_lock(self) -> None:
        """All four boolean-ish fields round-trip through builder + parser."""
        from custom_components.petkit_ble.ble_client import (
            PetkitBleClient,
            PetkitFountainData,
        )

        payload = bytes(
            build_settings_payload_ctw3(
                smart_work=7,
                smart_sleep=11,
                battery_work_time=300,
                battery_sleep_time=600,
                led_switch=1,
                led_brightness=6,
                dnd_enabled=1,
                child_lock=1,
            )
        )
        data = PetkitFountainData(alias="CTW3")
        PetkitBleClient._parse_config_ctw3(data, payload)
        assert data.smart_time_on == 7
        assert data.smart_time_off == 11
        assert data.battery_work_time == 300
        assert data.battery_sleep_time == 600
        assert data.do_not_disturb_switch == 1
        assert data.led_switch == 1
        assert data.led_brightness == 6
        assert data.is_locked == 1
        assert data.config_loaded is True


class TestBuildModePayload:
    """Tests for mode payload builders."""

    def test_w5_mode_payload(self) -> None:
        """W5 mode payload is [mode, submode]."""
        assert build_change_mode_payload(1, 0) == [1, 0]
        assert build_change_mode_payload(2, 1) == [2, 1]

    def test_ctw3_mode_payload(self) -> None:
        """CTW3 mode payload is [power, suspend, mode]."""
        assert build_ctw3_mode_payload(1, 0, 2) == [1, 0, 2]
        # When power=0, suspend is forced to 0 regardless of the argument passed
        assert build_ctw3_mode_payload(0, 1, 1) == [0, 0, 1]


class TestBuildCtw3SelectModePayload:
    """Tests for build_ctw3_select_mode_payload (regression for issue #54).

    Selecting a mode in HA must always send power=1, regardless of the cached
    ``power_status``. Otherwise Smart->Normal can silently send [0, 0, 1] and
    leave the pump off when byte[0] of CMD 210 was momentarily 0 during the
    smart-mode sleep cycle.
    """

    def test_select_normal_always_sends_power_on_with_suspend(self) -> None:
        """Selecting Normal => [1, 1, 1] (power on, pump active)."""
        assert build_ctw3_select_mode_payload(1) == [1, 1, 1]

    def test_select_smart_always_sends_power_on_without_suspend(self) -> None:
        """Selecting Smart => [1, 0, 2] (power on, timer-managed)."""
        assert build_ctw3_select_mode_payload(2) == [1, 0, 2]


class TestFrameFormat:
    """Tests for frame building via PetkitBleClient."""

    def test_build_frame(self) -> None:
        """Frame has correct header, metadata, payload, and end marker."""
        # Create client with a mock BLE device
        from unittest.mock import MagicMock

        from custom_components.petkit_ble.ble_client import PetkitBleClient

        client = PetkitBleClient(MagicMock())
        frame = client._build_frame(cmd=210, type_=1, seq=0, data=[0x01, 0x02])

        assert frame[:3] == FRAME_HEADER
        assert frame[3] == 210  # cmd
        assert frame[4] == 1  # type
        assert frame[5] == 0  # seq
        assert frame[6] == 2  # data_len
        assert frame[7] == 0x00  # reserved
        assert frame[8] == 0x01  # payload[0]
        assert frame[9] == 0x02  # payload[1]
        assert frame[10] == FRAME_END

    def test_parse_frame_roundtrip(self) -> None:
        """A built frame should parse back correctly."""
        from unittest.mock import MagicMock

        from custom_components.petkit_ble.ble_client import PetkitBleClient

        client = PetkitBleClient(MagicMock())
        frame = client._build_frame(cmd=84, type_=1, seq=5, data=[10, 20, 30])
        result = client._parse_frame(frame)
        assert result is not None
        cmd, type_, seq, payload = result
        assert cmd == 84
        assert type_ == 1
        assert seq == 5
        assert payload == bytes([10, 20, 30])

    def test_parse_frame_invalid_short(self) -> None:
        """Too-short frames return None."""
        from unittest.mock import MagicMock

        from custom_components.petkit_ble.ble_client import PetkitBleClient

        client = PetkitBleClient(MagicMock())
        assert client._parse_frame(b"\xfa\xfc") is None

    def test_parse_frame_invalid_header(self) -> None:
        """Frames with wrong header return None."""
        from unittest.mock import MagicMock

        from custom_components.petkit_ble.ble_client import PetkitBleClient

        client = PetkitBleClient(MagicMock())
        frame = bytes([0x00, 0x00, 0x00, 210, 1, 0, 0, 0, FRAME_END])
        assert client._parse_frame(frame) is None
