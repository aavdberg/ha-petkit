"""Petkit BLE protocol client."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import struct
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bleak import BleakClient
from bleak.backends.device import BLEDevice

from .const import (
    AUTH_STEP_DELAY,
    BLE_NOTIFY_UUID,
    BLE_WRITE_UUID,
    CMD_AUTH_INIT,
    CMD_AUTH_VERIFY,
    CMD_GET_BATTERY,
    CMD_GET_CONFIG,
    CMD_GET_DEVICE_INFO,
    CMD_GET_STATE,
    CMD_SET_TIME,
    CTW3_ALIASES,
    DEFAULT_FLOW_DIVISOR,
    DEFAULT_FLOW_RATE_LPM,
    DEFAULT_POWER_COEFF_W,
    FILTER_LIFE_NORMAL_DAYS,
    FILTER_LIFE_SMART_DAYS,
    FLOW_DIVISOR,
    FLOW_RATE_LPM,
    FRAME_END,
    FRAME_HEADER,
    FRAME_TYPE_SEND,
    PETKIT_EPOCH_OFFSET,
    POWER_COEFF_W,
    ZERO_DEVICE_ID_MODELS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PetkitFountainData:
    """Parsed state of a Petkit fountain."""

    alias: str = ""
    firmware: str = ""
    rssi: int | None = None

    # Power & mode (CMD 210)
    power_status: int = 0          # 0=off, 1=on
    mode: int = 1                  # 1=normal, 2=smart
    running_status: int = 0
    dnd_state: int = 0

    # Warnings
    warning_breakdown: int = 0
    warning_water_missing: int = 0
    warning_filter: int = 0

    # Pump runtime (seconds)
    pump_runtime: int = 0
    pump_runtime_today: int = 0

    # Filter
    filter_percent: int = 0

    # CTW3-specific fields
    suspend_status: int = 0
    electric_status: int = 0
    low_battery: int = 0
    detect_status: int = 0
    supply_voltage_mv: int = 0
    battery_voltage_mv: int = 0
    battery_percent: int = 0
    module_status: int = 0

    # CMD 211 config fields
    smart_time_on: int = 0         # minutes
    smart_time_off: int = 0        # minutes
    led_switch: int = 0
    led_brightness: int = 1
    do_not_disturb_switch: int = 0
    is_locked: int = 0

    # CMD 66 battery (for non-CTW3)
    battery_voltage_mv_66: int = 0
    battery_percent_66: int = 0

    @property
    def is_ctw3(self) -> bool:
        """Return True if device uses the CTW3 extended state format."""
        return self.alias in CTW3_ALIASES

    @property
    def is_pump_running(self) -> bool:
        """Return True when the pump is actively running."""
        return self.running_status == 1

    @property
    def filter_days_remaining(self) -> int:
        """Estimate remaining filter life in days."""
        if self.mode == 1:
            time_on, time_off = 1, 0
        else:
            time_on, time_off = self.smart_time_on, self.smart_time_off

        if time_on == 0:
            return math.ceil(self.filter_percent / 100 * FILTER_LIFE_NORMAL_DAYS)
        return math.ceil(
            ((self.filter_percent / 100 * FILTER_LIFE_SMART_DAYS) * (time_on + time_off))
            / time_on
        )

    @property
    def water_purified_today_liters(self) -> float:
        """Estimated water purified today in litres."""
        flow_rate = FLOW_RATE_LPM.get(self.alias, DEFAULT_FLOW_RATE_LPM)
        divisor = FLOW_DIVISOR.get(self.alias, DEFAULT_FLOW_DIVISOR)
        return (flow_rate * self.pump_runtime_today / 60) / divisor

    @property
    def energy_today_kwh(self) -> float:
        """Estimated energy used today in kWh."""
        coeff = POWER_COEFF_W.get(self.alias, DEFAULT_POWER_COEFF_W)
        return coeff * self.pump_runtime_today / 3600 / 1000


class PetkitBleClient:
    """BLE client for Petkit water fountains implementing the Petkit protocol."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialise with a discovered BLE device."""
        self._device = ble_device
        self._client: BleakClient | None = None
        self._rx_buf: bytearray = bytearray()
        self._rx_event: asyncio.Event = asyncio.Event()
        self._last_response: bytes | None = None
        self._seq: int = 0

    # ------------------------------------------------------------------
    # Frame encode / decode
    # ------------------------------------------------------------------

    def _build_frame(self, cmd: int, type_: int, seq: int, data: list[int]) -> bytes:
        """Build a Petkit protocol frame."""
        payload = bytes(data)
        frame = (
            FRAME_HEADER
            + bytes([cmd, type_, seq, len(payload), 0x00])
            + payload
            + bytes([FRAME_END])
        )
        return frame

    def _parse_frame(self, raw: bytes) -> tuple[int, int, int, bytes] | None:
        """Parse a complete Petkit frame.

        Returns (cmd, type_, seq, payload) or None if the frame is invalid.
        """
        if len(raw) < 9:
            return None
        if raw[:3] != FRAME_HEADER:
            return None
        if raw[-1] != FRAME_END:
            return None
        cmd = raw[3]
        type_ = raw[4]
        seq = raw[5]
        data_len = raw[6]
        # byte[7] is reserved
        payload = raw[8 : 8 + data_len]
        return cmd, type_, seq, payload

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return seq

    # ------------------------------------------------------------------
    # Notification handler (accumulates multi-packet responses)
    # ------------------------------------------------------------------

    def _on_notify(self, _sender: int, data: bytearray) -> None:
        """Handle incoming BLE notification data."""
        self._rx_buf.extend(data)
        if FRAME_END in self._rx_buf:
            self._last_response = bytes(self._rx_buf)
            self._rx_buf.clear()
            self._rx_event.set()

    # ------------------------------------------------------------------
    # Low-level send/receive
    # ------------------------------------------------------------------

    async def _send_and_wait(
        self,
        cmd: int,
        type_: int,
        data: list[int],
        timeout: float = 5.0,
    ) -> bytes | None:
        """Send a command frame and wait for the matching response."""
        assert self._client is not None
        seq = self._next_seq()
        frame = self._build_frame(cmd, type_, seq, data)
        self._rx_event.clear()
        self._last_response = None
        await self._client.write_gatt_char(BLE_WRITE_UUID, frame, response=False)
        try:
            await asyncio.wait_for(self._rx_event.wait(), timeout)
        except TimeoutError:
            _LOGGER.warning("Timeout waiting for response to CMD %d", cmd)
            return None

        raw = self._last_response
        if raw is None:
            return None
        parsed = self._parse_frame(raw)
        if parsed is None:
            _LOGGER.debug("Could not parse response frame for CMD %d: %s", cmd, raw.hex())
            return None
        _resp_cmd, _resp_type, _resp_seq, payload = parsed
        return payload

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish BLE connection and start notifications."""
        self._client = BleakClient(self._device)
        await self._client.connect()
        await self._client.start_notify(BLE_NOTIFY_UUID, self._on_notify)
        self._rx_buf.clear()
        self._seq = 0

    async def disconnect(self) -> None:
        """Disconnect from the device, suppressing cleanup errors."""
        if self._client is None:
            return
        with contextlib.suppress(Exception):
            await self._client.stop_notify(BLE_NOTIFY_UUID)
        with contextlib.suppress(Exception):
            await self._client.disconnect()
        self._client = None

    # ------------------------------------------------------------------
    # Authentication sequence
    # ------------------------------------------------------------------

    async def _authenticate(self, alias: str) -> None:
        """Run the full 5-step Petkit authentication sequence."""
        # Step 1: CMD 213 — get device id & serial
        payload_213 = await self._send_and_wait(CMD_GET_DEVICE_INFO, FRAME_TYPE_SEND, [0, 0])
        if payload_213 is None or len(payload_213) < 23:
            raise RuntimeError("CMD 213 failed or response too short")

        device_id_bytes = list(payload_213[2:8])
        # serial = payload_213[8:23]  # available if needed

        # Step 2: Compute secret
        # CTW3 always uses all-zero device_id for secret computation
        secret_source = [0] * 6 if alias in ZERO_DEVICE_ID_MODELS else device_id_bytes

        secret = list(reversed(secret_source))
        if secret[-1] == 0 and secret[-2] == 0:
            secret[-2] = 13
            secret[-1] = 37
        # Pad left to 8 bytes
        secret = [*([0] * (8 - len(secret))), *secret]

        # device_id padded to 8 bytes (left-pad with zeros)
        device_id_padded = [*([0] * (8 - len(device_id_bytes))), *device_id_bytes]

        await asyncio.sleep(AUTH_STEP_DELAY)

        # Step 3: CMD 73
        await self._send_and_wait(
            CMD_AUTH_INIT,
            FRAME_TYPE_SEND,
            [0, 0, *device_id_padded, *secret],
        )
        await asyncio.sleep(AUTH_STEP_DELAY)

        # Step 4: CMD 86 — verify auth; response[0]==1 means success
        payload_86 = await self._send_and_wait(
            CMD_AUTH_VERIFY, FRAME_TYPE_SEND, [0, 0, *secret]
        )
        await asyncio.sleep(AUTH_STEP_DELAY)
        if payload_86 is None or len(payload_86) == 0 or payload_86[0] != 1:
            raise RuntimeError(
                "Authentication failed (CMD 86 response: %s)"
                % (payload_86.hex() if payload_86 else "None")
            )

        # Step 5: CMD 84 — set device time
        sec = int(time.time()) - PETKIT_EPOCH_OFFSET
        time_bytes = [
            0,
            (sec >> 24) & 0xFF,
            (sec >> 16) & 0xFF,
            (sec >> 8) & 0xFF,
            sec & 0xFF,
            13,
        ]
        await self._send_and_wait(CMD_SET_TIME, FRAME_TYPE_SEND, time_bytes)
        await asyncio.sleep(AUTH_STEP_DELAY)

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_state_ctw3(data: PetkitFountainData, payload: bytes) -> None:
        """Parse CMD 210 response for CTW3 (26+ bytes)."""
        if len(payload) < 26:
            _LOGGER.warning("CTW3 state payload too short: %d bytes", len(payload))
            return
        data.power_status = payload[0]
        data.suspend_status = payload[1]
        data.mode = payload[2]
        data.electric_status = payload[3]
        data.dnd_state = payload[4]
        data.warning_breakdown = payload[5]
        data.warning_water_missing = payload[6]
        data.low_battery = payload[7]
        data.warning_filter = payload[8]
        data.pump_runtime = struct.unpack_from(">I", payload, 9)[0]
        data.filter_percent = payload[13]
        data.running_status = payload[14]
        data.pump_runtime_today = struct.unpack_from(">I", payload, 15)[0]
        data.detect_status = payload[19]
        data.supply_voltage_mv = struct.unpack_from(">h", payload, 20)[0]
        data.battery_voltage_mv = struct.unpack_from(">h", payload, 22)[0]
        data.battery_percent = payload[24]
        data.module_status = payload[25]

    @staticmethod
    def _parse_state_generic(data: PetkitFountainData, payload: bytes) -> None:
        """Parse CMD 210 response for W4/W5/CTW2 (12+ bytes)."""
        if len(payload) < 12:
            _LOGGER.warning("State payload too short: %d bytes", len(payload))
            return
        data.power_status = payload[0]
        data.mode = payload[1]
        data.dnd_state = payload[2]
        data.warning_breakdown = payload[3]
        data.warning_water_missing = payload[4]
        data.warning_filter = payload[5]
        data.pump_runtime = struct.unpack_from(">I", payload, 6)[0]
        data.filter_percent = payload[10]
        data.running_status = payload[11]
        if len(payload) >= 16:
            data.pump_runtime_today = struct.unpack_from(">I", payload, 12)[0]
        if len(payload) >= 17:
            data.smart_time_on = payload[16]
        if len(payload) >= 18:
            data.smart_time_off = payload[17]

    @staticmethod
    def _parse_config_ctw3(data: PetkitFountainData, payload: bytes) -> None:
        """Parse CMD 211 response for CTW3."""
        if len(payload) < 9:
            return
        data.smart_time_on = payload[0]
        data.smart_time_off = payload[1]
        # payload[2:4] battery_working_time, payload[4:6] battery_sleep_time — informational
        data.led_switch = payload[6]
        data.led_brightness = payload[7]
        data.do_not_disturb_switch = payload[8]
        if len(payload) >= 10:
            data.is_locked = payload[9]

    @staticmethod
    def _parse_config_generic(data: PetkitFountainData, payload: bytes) -> None:
        """Parse CMD 211 response for W4/W5/CTW2."""
        if len(payload) < 9:
            return
        data.smart_time_on = payload[0]
        data.smart_time_off = payload[1]
        data.led_switch = payload[2]
        data.led_brightness = payload[3]
        # payload[4:6] led_light_time_on, [6:8] led_light_time_off — informational
        data.do_not_disturb_switch = payload[8]
        if len(payload) >= 14:
            data.is_locked = payload[13]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def async_poll(self, alias: str) -> PetkitFountainData:
        """Connect, authenticate, poll all state commands, disconnect.

        Returns a fully-populated PetkitFountainData instance.
        """
        data = PetkitFountainData(alias=alias)
        try:
            await self._connect()
            await self._authenticate(alias)

            # CMD 210 — device state
            payload_210 = await self._send_and_wait(CMD_GET_STATE, FRAME_TYPE_SEND, [0, 0])
            if payload_210 is not None:
                if alias in CTW3_ALIASES:
                    self._parse_state_ctw3(data, payload_210)
                else:
                    self._parse_state_generic(data, payload_210)

            # CMD 211 — device config
            payload_211 = await self._send_and_wait(CMD_GET_CONFIG, FRAME_TYPE_SEND, [0, 0])
            if payload_211 is not None:
                if alias in CTW3_ALIASES:
                    self._parse_config_ctw3(data, payload_211)
                else:
                    self._parse_config_generic(data, payload_211)

            # CMD 66 — battery (mainly for non-CTW3)
            payload_66 = await self._send_and_wait(CMD_GET_BATTERY, FRAME_TYPE_SEND, [0, 0])
            if payload_66 is not None and len(payload_66) >= 3:
                data.battery_voltage_mv_66 = payload_66[0] * 256 + (payload_66[1] & 0xFF)
                data.battery_percent_66 = payload_66[2]

        finally:
            await self.disconnect()

        return data

    async def async_send_command(
        self,
        cmd: int,
        data: list[int],
        alias: str,
    ) -> bool:
        """Connect, authenticate, send a single command, disconnect.

        Returns True on success.
        """
        try:
            await self._connect()
            await self._authenticate(alias)
            await self._send_and_wait(cmd, FRAME_TYPE_SEND, data)
        except Exception:
            _LOGGER.exception("Error sending CMD %d", cmd)
            return False
        finally:
            await self.disconnect()
        return True
