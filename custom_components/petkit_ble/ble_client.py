"""Petkit BLE protocol client."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import secrets
import struct
import time
from dataclasses import dataclass

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .const import (
    AUTH_STEP_DELAY,
    BLE_NOTIFY_UUID,
    BLE_WRITE_UUID,
    CMD_AUTH_INIT,
    CMD_AUTH_VERIFY,
    CMD_GET_BATTERY,
    CMD_GET_CONFIG,
    CMD_GET_DEVICE_INFO,
    CMD_GET_FIRMWARE,
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
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PetkitFountainData:
    """Parsed state of a Petkit fountain."""

    alias: str = ""
    firmware: str = ""
    hardware_version: str = ""
    rssi: int | None = None

    # Power & mode (CMD 210)
    power_status: int = 0  # 0=off, 1=on
    mode: int = 1  # 1=normal, 2=smart
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
    smart_time_on: int = 0  # minutes
    smart_time_off: int = 0  # minutes
    led_switch: int = 0
    led_brightness: int = 1
    do_not_disturb_switch: int = 0
    is_locked: int = 0

    # CMD 66 battery (raw ADC voltage, little-endian, for non-CTW3)
    battery_voltage_mv_66: int = 0

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
        return math.ceil(((self.filter_percent / 100 * FILTER_LIFE_SMART_DAYS) * (time_on + time_off)) / time_on)

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
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._seq: int = 0
        self.used_secret: bytes | None = None

    # ------------------------------------------------------------------
    # Frame encode / decode
    # ------------------------------------------------------------------

    def _build_frame(self, cmd: int, type_: int, seq: int, data: list[int]) -> bytes:
        """Build a Petkit protocol frame."""
        payload = bytes(data)
        frame = FRAME_HEADER + bytes([cmd, type_, seq, len(payload), 0x00]) + payload + bytes([FRAME_END])
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
        # Need at least header(3) + cmd/type/seq/len/reserved(5) = 8 bytes to read length
        if len(self._rx_buf) < 8:
            return
        data_len = self._rx_buf[6]
        # Total frame = header(3) + meta(5) + payload(data_len) + end(1)
        expected_len = 8 + data_len + 1
        if len(self._rx_buf) >= expected_len and self._rx_buf[expected_len - 1] == FRAME_END:
            self._rx_queue.put_nowait(bytes(self._rx_buf[:expected_len]))
            del self._rx_buf[:expected_len]

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
        """Send a command frame and wait for the matching response.

        Unsolicited notifications with a different cmd byte (e.g. CTW3 CMD 230
        extended state pushes) are discarded while waiting for the expected reply.
        """
        assert self._client is not None
        seq = self._next_seq()
        frame = self._build_frame(cmd, type_, seq, data)
        await self._client.write_gatt_char(BLE_WRITE_UUID, frame, response=False)
        _LOGGER.debug("TX CMD %d: %s", cmd, frame.hex())
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                _LOGGER.warning("Timeout waiting for response to CMD %d", cmd)
                return None
            try:
                raw = await asyncio.wait_for(self._rx_queue.get(), remaining)
            except TimeoutError:
                _LOGGER.warning("Timeout waiting for response to CMD %d", cmd)
                return None
            parsed = self._parse_frame(raw)
            if parsed is None:
                _LOGGER.debug("Could not parse frame while waiting for CMD %d: %s", cmd, raw.hex())
                continue
            resp_cmd, _resp_type, _resp_seq, payload = parsed
            if resp_cmd != cmd:
                _LOGGER.debug(
                    "Discarding unsolicited CMD %d notification while waiting for CMD %d",
                    resp_cmd,
                    cmd,
                )
                continue
            _LOGGER.debug("RX CMD %d: %s", cmd, raw.hex())
            return payload

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Establish BLE connection using bleak-retry-connector for reliability."""
        self._client = await establish_connection(
            BleakClient,
            self._device,
            self._device.address,
        )
        await self._client.start_notify(BLE_NOTIFY_UUID, self._on_notify)
        self._rx_buf.clear()
        # Discard any stale notifications from a previous connection
        while not self._rx_queue.empty():
            self._rx_queue.get_nowait()
        self._seq = 0
        # Allow device time to settle before sending first command
        await asyncio.sleep(0.5)

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

    async def _authenticate(self, alias: str, secret: bytes | None = None) -> None:
        """Run the Petkit authentication sequence.

        On first connection (secret=None), fetches the device ID, generates a random
        8-byte secret, initialises the device with CMD 73, then verifies with CMD 86.
        The generated secret is stored in self.used_secret for the coordinator to persist.

        On subsequent connections, verifies directly with CMD 86 using the stored secret.
        """
        if secret is None:
            # First-time initialisation: fetch device ID and generate a random secret
            payload_213 = await self._send_and_wait(CMD_GET_DEVICE_INFO, FRAME_TYPE_SEND, [])
            if payload_213 is None or len(payload_213) < 8:
                byte_count = len(payload_213) if payload_213 is not None else 0
                raise RuntimeError(f"CMD 213 failed or response too short (got {byte_count} bytes)")
            # Convert device_id bytes to big-endian for CMD 73 payload
            device_id_be = struct.pack(">q", int.from_bytes(payload_213[:8], "little"))
            new_secret = secrets.token_bytes(8)

            await asyncio.sleep(AUTH_STEP_DELAY)
            await self._send_and_wait(CMD_AUTH_INIT, FRAME_TYPE_SEND, list(device_id_be) + list(new_secret))
            await asyncio.sleep(AUTH_STEP_DELAY)

            auth_secret = new_secret
            _LOGGER.debug("First-time device initialisation complete for %s", alias)
        else:
            auth_secret = secret

        # CMD 86 — verify secret; response[0]==1 means success
        payload_86 = await self._send_and_wait(CMD_AUTH_VERIFY, FRAME_TYPE_SEND, list(auth_secret))
        await asyncio.sleep(AUTH_STEP_DELAY)
        if payload_86 is None or len(payload_86) == 0 or payload_86[0] != 1:
            resp_hex = payload_86.hex() if payload_86 else "None"
            raise RuntimeError(f"Authentication failed (CMD 86 response: {resp_hex})")

        self.used_secret = auth_secret

        # CMD 84 — set device time
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

    async def async_poll(self, alias: str, secret: bytes | None = None) -> PetkitFountainData:
        """Connect, authenticate, poll all state commands, disconnect.

        Returns a fully-populated PetkitFountainData instance.
        The generated or used secret is stored in self.used_secret after success.
        """
        data = PetkitFountainData(alias=alias)
        try:
            await self._connect()
            await self._authenticate(alias, secret)

            # CMD 200 — firmware version: byte[0]=hardware revision, byte[1]=firmware version
            payload_200 = await self._send_and_wait(CMD_GET_FIRMWARE, FRAME_TYPE_SEND, [])
            if payload_200 is not None and len(payload_200) >= 2:
                data.hardware_version = str(payload_200[0])
                data.firmware = str(payload_200[1])
                _LOGGER.debug(
                    "CMD 200 firmware payload: %s → hw=%s fw=%s",
                    payload_200.hex(),
                    data.hardware_version,
                    data.firmware,
                )

            # CMD 210 — device state
            payload_210 = await self._send_and_wait(CMD_GET_STATE, FRAME_TYPE_SEND, [])
            if payload_210 is not None:
                if alias in CTW3_ALIASES:
                    self._parse_state_ctw3(data, payload_210)
                else:
                    self._parse_state_generic(data, payload_210)

            # CMD 211 — device config (not supported by CTW3: device does not respond)
            if alias not in CTW3_ALIASES:
                payload_211 = await self._send_and_wait(CMD_GET_CONFIG, FRAME_TYPE_SEND, [])
                if payload_211 is not None:
                    self._parse_config_generic(data, payload_211)

            # CMD 66 — raw ADC voltage (2 bytes little-endian per protocol spec)
            payload_66 = await self._send_and_wait(CMD_GET_BATTERY, FRAME_TYPE_SEND, [0, 0])
            if payload_66 is not None and len(payload_66) >= 2:
                data.battery_voltage_mv_66 = payload_66[0] + payload_66[1] * 256

        finally:
            await self.disconnect()

        return data

    async def async_send_command(
        self,
        cmd: int,
        data: list[int],
        alias: str,
        secret: bytes | None = None,
    ) -> bool:
        """Connect, authenticate, send a single command, disconnect.

        Returns True on success.
        """
        try:
            await self._connect()
            await self._authenticate(alias, secret)
            await self._send_and_wait(cmd, FRAME_TYPE_SEND, data)
        except Exception:
            _LOGGER.exception("Error sending CMD %d", cmd)
            return False
        finally:
            await self.disconnect()
        return True
