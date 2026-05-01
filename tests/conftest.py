"""Shared fixtures for Petkit BLE tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure the custom_components package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub out homeassistant modules that are not available in a plain pytest run
_HA_STUBS = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.bluetooth",
    "homeassistant.components.number",
    "homeassistant.components.select",
    "homeassistant.components.sensor",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.button",
    "homeassistant.components.switch",
    "homeassistant.components.time",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.storage",
    "homeassistant.helpers.update_coordinator",
    "bleak",
    "bleak.backends",
    "bleak.backends.device",
    "bleak_retry_connector",
    "voluptuous",
]

for mod_name in _HA_STUBS:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def sample_ctw3_state_payload() -> bytes:
    """Return a sample 26-byte CTW3 CMD 210 state payload."""
    import struct

    buf = bytearray(26)
    buf[0] = 1  # power_status
    buf[1] = 0  # suspend_status
    buf[2] = 2  # mode (smart)
    buf[3] = 2  # electric_status (AC)
    buf[4] = 0  # dnd_state
    buf[5] = 0  # warning_breakdown
    buf[6] = 0  # warning_water_missing
    buf[7] = 0  # low_battery
    buf[8] = 0  # warning_filter
    struct.pack_into(">I", buf, 9, 3600)  # pump_runtime
    buf[13] = 80  # filter_percent
    buf[14] = 1  # running_status
    struct.pack_into(">I", buf, 15, 1800)  # pump_runtime_today
    buf[19] = 1  # detect_status
    struct.pack_into(">h", buf, 20, 5000)  # supply_voltage_mv
    struct.pack_into(">h", buf, 22, 4200)  # battery_voltage_mv
    buf[24] = 85  # battery_percent
    buf[25] = 0x01  # module_status (UVC active)
    return bytes(buf)


@pytest.fixture
def sample_generic_state_payload() -> bytes:
    """Return a sample 18-byte generic CMD 210 state payload."""
    import struct

    buf = bytearray(18)
    buf[0] = 1  # power_status
    buf[1] = 1  # mode (normal)
    buf[2] = 0  # dnd_state
    buf[3] = 0  # warning_breakdown
    buf[4] = 0  # warning_water_missing
    buf[5] = 0  # warning_filter
    struct.pack_into(">I", buf, 6, 7200)  # pump_runtime
    buf[10] = 60  # filter_percent
    buf[11] = 0  # running_status
    struct.pack_into(">I", buf, 12, 900)  # pump_runtime_today
    buf[16] = 5  # smart_time_on
    buf[17] = 10  # smart_time_off
    return bytes(buf)
