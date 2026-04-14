"""Tests for PetkitFountainData calculated properties."""

from __future__ import annotations

import math

import pytest

from custom_components.petkit_ble.ble_client import PetkitBleClient, PetkitFountainData
from custom_components.petkit_ble.const import (
    ALIAS_CTW3,
    ALIAS_W5,
    ALIAS_W5C,
)


class TestIsCtw3:
    """Tests for is_ctw3 property."""

    def test_ctw3_alias(self) -> None:
        data = PetkitFountainData(alias=ALIAS_CTW3)
        assert data.is_ctw3 is True

    def test_non_ctw3_alias(self) -> None:
        data = PetkitFountainData(alias=ALIAS_W5)
        assert data.is_ctw3 is False

    def test_empty_alias(self) -> None:
        data = PetkitFountainData(alias="")
        assert data.is_ctw3 is False


class TestIsPumpRunning:
    """Tests for is_pump_running property."""

    def test_running(self) -> None:
        data = PetkitFountainData(running_status=1)
        assert data.is_pump_running is True

    def test_not_running(self) -> None:
        data = PetkitFountainData(running_status=0)
        assert data.is_pump_running is False


class TestFilterDaysRemaining:
    """Tests for filter_days_remaining property."""

    def test_normal_mode_full(self) -> None:
        """100% filter in normal mode → ceil(1.0 * 60) = 60 days."""
        data = PetkitFountainData(mode=1, filter_percent=100)
        assert data.filter_days_remaining == 60

    def test_normal_mode_half(self) -> None:
        """50% filter in normal mode → ceil(0.5 * 60) = 30 days."""
        data = PetkitFountainData(mode=1, filter_percent=50)
        assert data.filter_days_remaining == 30

    def test_smart_mode(self) -> None:
        """Smart mode with on=5, off=10 → ceil((pct/100 * 30) * (5+10) / 5)."""
        data = PetkitFountainData(mode=2, filter_percent=100, smart_time_on=5, smart_time_off=10)
        expected = math.ceil((100 / 100 * 30) * (5 + 10) / 5)
        assert data.filter_days_remaining == expected

    def test_smart_mode_zero_on(self) -> None:
        """Smart mode with on=0 falls back to normal calculation."""
        data = PetkitFountainData(mode=2, filter_percent=80, smart_time_on=0, smart_time_off=10)
        expected = math.ceil(80 / 100 * 60)
        assert data.filter_days_remaining == expected


class TestWaterPurifiedToday:
    """Tests for water_purified_today_liters property."""

    def test_default_alias(self) -> None:
        """Default alias uses default flow rate and divisor."""
        data = PetkitFountainData(alias=ALIAS_W5, pump_runtime_today=3600)
        result = data.water_purified_today_liters
        # flow_rate=1.5, divisor=2.0 → (1.5 * 3600 / 60) / 2.0 = 45.0
        assert result == pytest.approx(45.0)

    def test_w5c_alias(self) -> None:
        """W5C has specific flow rate and divisor."""
        data = PetkitFountainData(alias=ALIAS_W5C, pump_runtime_today=3600)
        result = data.water_purified_today_liters
        # flow_rate=1.3, divisor=1.0 → (1.3 * 3600 / 60) / 1.0 = 78.0
        assert result == pytest.approx(78.0)

    def test_ctw3_alias(self) -> None:
        """CTW3 has a divisor of 3.0."""
        data = PetkitFountainData(alias=ALIAS_CTW3, pump_runtime_today=1800)
        result = data.water_purified_today_liters
        # flow_rate=1.5, divisor=3.0 → (1.5 * 1800 / 60) / 3.0 = 15.0
        assert result == pytest.approx(15.0)

    def test_zero_runtime(self) -> None:
        data = PetkitFountainData(alias=ALIAS_W5, pump_runtime_today=0)
        assert data.water_purified_today_liters == 0.0


class TestEnergyTodayKwh:
    """Tests for energy_today_kwh property."""

    def test_default(self) -> None:
        """Default power coefficient is 0.75 W."""
        data = PetkitFountainData(alias=ALIAS_W5, pump_runtime_today=3600)
        # 0.75 * 3600 / 3600 / 1000 = 0.00075
        assert data.energy_today_kwh == pytest.approx(0.00075)

    def test_w5c(self) -> None:
        """W5C power coefficient is 0.182 W."""
        data = PetkitFountainData(alias=ALIAS_W5C, pump_runtime_today=3600)
        assert data.energy_today_kwh == pytest.approx(0.182 * 3600 / 3600 / 1000)


class TestStateParsers:
    """Tests for state payload parsers."""

    def test_parse_state_ctw3(self, sample_ctw3_state_payload: bytes) -> None:
        """Parse a CTW3 state payload and verify all fields."""
        data = PetkitFountainData(alias=ALIAS_CTW3)
        PetkitBleClient._parse_state_ctw3(data, sample_ctw3_state_payload)

        assert data.power_status == 1
        assert data.suspend_status == 0
        assert data.mode == 2
        assert data.electric_status == 2
        assert data.pump_runtime == 3600
        assert data.filter_percent == 80
        assert data.running_status == 1
        assert data.pump_runtime_today == 1800
        assert data.detect_status == 1
        assert data.battery_percent == 85
        assert data.module_status == 0x01

    def test_parse_state_generic(self, sample_generic_state_payload: bytes) -> None:
        """Parse a generic state payload and verify fields."""
        data = PetkitFountainData(alias=ALIAS_W5)
        PetkitBleClient._parse_state_generic(data, sample_generic_state_payload)

        assert data.power_status == 1
        assert data.mode == 1
        assert data.pump_runtime == 7200
        assert data.filter_percent == 60
        assert data.running_status == 0
        assert data.pump_runtime_today == 900
        assert data.smart_time_on == 5
        assert data.smart_time_off == 10

    def test_parse_config_generic(self) -> None:
        """Parse a generic CMD 211 config payload."""
        import struct

        buf = bytearray(14)
        buf[0] = 5  # smart_work
        buf[1] = 10  # smart_sleep
        buf[2] = 1  # led_switch
        buf[3] = 7  # led_brightness
        struct.pack_into(">H", buf, 4, 480)  # led_on_minutes
        struct.pack_into(">H", buf, 6, 1320)  # led_off_minutes
        buf[8] = 1  # dnd_enabled
        struct.pack_into(">H", buf, 9, 1380)  # dnd_start
        struct.pack_into(">H", buf, 11, 420)  # dnd_end
        buf[13] = 1  # child_lock

        data = PetkitFountainData(alias=ALIAS_W5)
        PetkitBleClient._parse_config_generic(data, bytes(buf))

        assert data.smart_time_on == 5
        assert data.smart_time_off == 10
        assert data.led_switch == 1
        assert data.led_brightness == 7
        assert data.led_on_minutes == 480
        assert data.led_off_minutes == 1320
        assert data.do_not_disturb_switch == 1
        assert data.dnd_start_minutes == 1380
        assert data.dnd_end_minutes == 420
        assert data.is_locked == 1

    def test_parse_config_ctw3(self) -> None:
        """Parse a CTW3 CMD 211 config payload."""
        import struct

        buf = bytearray(10)
        buf[0] = 3  # smart_work
        buf[1] = 7  # smart_sleep
        struct.pack_into(">H", buf, 2, 300)  # battery_work_time
        struct.pack_into(">H", buf, 4, 600)  # battery_sleep_time
        buf[6] = 1  # led_switch
        buf[7] = 5  # led_brightness
        buf[8] = 1  # dnd_enabled
        buf[9] = 0  # child_lock

        data = PetkitFountainData(alias=ALIAS_CTW3)
        PetkitBleClient._parse_config_ctw3(data, bytes(buf))

        assert data.smart_time_on == 3
        assert data.smart_time_off == 7
        assert data.battery_work_time == 300
        assert data.battery_sleep_time == 600
        assert data.led_switch == 1
        assert data.led_brightness == 5
        assert data.do_not_disturb_switch == 1
        assert data.is_locked == 0


class TestDrinkEventCount:
    """Tests for drink_event_count field."""

    def test_default_zero(self) -> None:
        data = PetkitFountainData()
        assert data.drink_event_count == 0

    def test_can_be_set(self) -> None:
        data = PetkitFountainData(drink_event_count=5)
        assert data.drink_event_count == 5
