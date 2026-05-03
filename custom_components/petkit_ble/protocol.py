"""Payload builders and decoders for the Petkit BLE protocol."""

from __future__ import annotations

import struct
import time
from typing import TYPE_CHECKING

from .const import CTW3_ALIASES, PETKIT_EPOCH_OFFSET

if TYPE_CHECKING:
    from .ble_client import PetkitFountainData


def build_time_sync_payload() -> list[int]:
    """Build the 6-byte payload for CMD 84 (set device time).

    Layout: [0, sec>>24, sec>>16, sec>>8, sec, 13]
    where sec = seconds since the Petkit epoch (2000-01-01 UTC).
    """
    sec = int(time.time()) - PETKIT_EPOCH_OFFSET
    return [
        0,
        (sec >> 24) & 0xFF,
        (sec >> 16) & 0xFF,
        (sec >> 8) & 0xFF,
        sec & 0xFF,
        13,
    ]


def build_init_payload(device_id: int, secret: bytes) -> list[int]:
    """Build the 16-byte payload for CMD 73 (device init).

    Layout: 8-byte device_id (big-endian unsigned) + 8-byte secret.
    """
    id_bytes = list(struct.pack(">Q", device_id))
    padded_secret = list(secret[:8].ljust(8, b"\x00"))
    return id_bytes + padded_secret


def build_full_settings_payload(data: PetkitFountainData, **overrides: int) -> list[int]:
    """Build a CMD 221 payload from current data with field overrides.

    This is the single shared helper used by switch, number, and time platforms.
    """
    if data.alias in CTW3_ALIASES:
        return build_settings_payload_ctw3(
            smart_work=overrides.get("smart_time_on", data.smart_time_on),
            smart_sleep=overrides.get("smart_time_off", data.smart_time_off),
            battery_work_time=overrides.get("battery_work_time", data.battery_work_time),
            battery_sleep_time=overrides.get("battery_sleep_time", data.battery_sleep_time),
            led_switch=overrides.get("led_switch", data.led_switch),
            led_brightness=overrides.get("led_brightness", data.led_brightness),
            dnd_enabled=overrides.get("do_not_disturb_switch", data.do_not_disturb_switch),
            child_lock=overrides.get("is_locked", data.is_locked),
        )
    return build_settings_payload_generic(
        smart_work=overrides.get("smart_time_on", data.smart_time_on),
        smart_sleep=overrides.get("smart_time_off", data.smart_time_off),
        led_switch=overrides.get("led_switch", data.led_switch),
        led_brightness=overrides.get("led_brightness", data.led_brightness),
        led_on_minutes=overrides.get("led_on_minutes", data.led_on_minutes),
        led_off_minutes=overrides.get("led_off_minutes", data.led_off_minutes),
        dnd_enabled=overrides.get("do_not_disturb_switch", data.do_not_disturb_switch),
        dnd_start_minutes=overrides.get("dnd_start_minutes", data.dnd_start_minutes),
        dnd_end_minutes=overrides.get("dnd_end_minutes", data.dnd_end_minutes),
        child_lock=overrides.get("is_locked", data.is_locked),
    )


def build_settings_payload_ctw3(
    smart_work: int,
    smart_sleep: int,
    battery_work_time: int = 0,
    battery_sleep_time: int = 0,
    led_switch: int = 0,
    led_brightness: int = 1,
    dnd_enabled: int = 0,
    child_lock: int = 0,
) -> list[int]:
    """Build the payload for CMD 221 (write settings) for CTW3 devices.

    Layout: [smart_work, smart_sleep, batt_work_hi, batt_work_lo,
             batt_sleep_hi, batt_sleep_lo, dnd_enabled, led_switch,
             led_brightness, child_lock]

    Reverse-engineered from real-device CMD 221 captures:
    confirmed user actions ``LED on -> brightness 1/8/9 -> LED off`` map
    cleanly to ``payload[7] = led_switch`` and ``payload[8] = led_brightness``.
    ``payload[6]`` is assumed to be ``dnd_enabled`` by analogy with the
    generic (W5/CTW2) layout; this could not be exercised by the captures
    (always 0) and may be re-validated when a CTW3 firmware response to
    CMD 211 becomes available.
    """
    return [
        smart_work,
        smart_sleep,
        (battery_work_time >> 8) & 0xFF,
        battery_work_time & 0xFF,
        (battery_sleep_time >> 8) & 0xFF,
        battery_sleep_time & 0xFF,
        dnd_enabled,
        led_switch,
        led_brightness,
        child_lock,
    ]


def build_settings_payload_generic(
    smart_work: int,
    smart_sleep: int,
    led_switch: int = 0,
    led_brightness: int = 1,
    led_on_minutes: int = 0,
    led_off_minutes: int = 0,
    dnd_enabled: int = 0,
    dnd_start_minutes: int = 0,
    dnd_end_minutes: int = 0,
    child_lock: int = 0,
) -> list[int]:
    """Build the payload for CMD 221 (write settings) for W5/CTW2 devices.

    Layout: [smart_work, smart_sleep, led_switch, led_brightness,
             led_on_hi, led_on_lo, led_off_hi, led_off_lo,
             dnd_enabled, dnd_start_hi, dnd_start_lo, dnd_end_hi, dnd_end_lo,
             child_lock]
    """
    return [
        smart_work,
        smart_sleep,
        led_switch,
        led_brightness,
        (led_on_minutes >> 8) & 0xFF,
        led_on_minutes & 0xFF,
        (led_off_minutes >> 8) & 0xFF,
        led_off_minutes & 0xFF,
        dnd_enabled,
        (dnd_start_minutes >> 8) & 0xFF,
        dnd_start_minutes & 0xFF,
        (dnd_end_minutes >> 8) & 0xFF,
        dnd_end_minutes & 0xFF,
        child_lock,
    ]


def build_change_mode_payload(mode: int, submode: int = 0) -> list[int]:
    """Build the payload for CMD 220 (change mode) for W5/CTW2 devices.

    Layout: [mode, submode]
    """
    return [mode, submode]


def build_ctw3_mode_payload(power: int, suspend: int, mode: int) -> list[int]:
    """Build the payload for CMD 220 (change mode) for CTW3 devices.

    Layout: [power, suspend, mode]

    The suspend byte controls pump activation:
      - 1 = pump active (required for normal mode to run)
      - 0 = timer-managed (smart mode handles its own cycling)
    When powering off, suspend is always forced to 0.
    """
    if power == 0:
        suspend = 0
    return [power, suspend, mode]


def build_ctw3_select_mode_payload(mode: int) -> list[int]:
    """Build a CMD 220 payload for a user mode-select on CTW3.

    Selecting a mode in the HA UI always implies power=1: the user expects
    that mode to *run*. We deliberately ignore the cached ``power_status``
    here because byte[0] of CMD 210 can momentarily be reported as 0 while
    the device is in smart-mode sleep cycle. Coupling the mode select to
    that cached value caused Smart→Normal to silently send [0, 0, 1] and
    leave the pump off.

    Returns:
      - Normal (mode=1): [1, 1, 1]  (power on, pump active)
      - Smart  (mode=2): [1, 0, 2]  (power on, timer-managed)
    """
    suspend = 1 if mode == 1 else 0
    return build_ctw3_mode_payload(1, suspend, mode)
