"""Shared fixtures for Petkit BLE tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
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
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.storage",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "homeassistant.util.dt",
    "bleak",
    "bleak.backends",
    "bleak.backends.device",
    "bleak.exc",
    "bleak_retry_connector",
    "voluptuous",
]

from dataclasses import dataclass  # noqa: E402

for mod_name in _HA_STUBS:
    if mod_name not in sys.modules:
        mod = MagicMock()
        mod.__path__ = []
        sys.modules[mod_name] = mod


class StubEntity:
    """Stub base class for Home Assistant entity classes in plain pytest runs."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __class_getitem__(cls, item: Any) -> type:
        return cls


@dataclass(frozen=True, kw_only=True)
class StubEntityDescription:
    """Stub entity description for plain pytest runs."""

    key: str
    translation_key: str | None = None
    device_class: Any = None
    entity_category: Any = None
    native_unit_of_measurement: Any = None
    state_class: Any = None
    icon: str | None = None
    options: list[str] | None = None
    native_max_value: float | None = None
    native_min_value: float | None = None
    native_step: float | None = None
    suggested_display_precision: int | None = None
    entity_registry_enabled_default: bool = True
    mode: Any = None


for module_key, class_name in [
    ("homeassistant.helpers.update_coordinator", "CoordinatorEntity"),
    ("homeassistant.components.binary_sensor", "BinarySensorEntity"),
    ("homeassistant.components.number", "NumberEntity"),
    ("homeassistant.components.select", "SelectEntity"),
    ("homeassistant.components.sensor", "SensorEntity"),
    ("homeassistant.components.button", "ButtonEntity"),
    ("homeassistant.components.switch", "SwitchEntity"),
    ("homeassistant.components.time", "TimeEntity"),
]:
    setattr(sys.modules[module_key], class_name, StubEntity)

for module_key, class_name in [
    ("homeassistant.components.binary_sensor", "BinarySensorEntityDescription"),
    ("homeassistant.components.number", "NumberEntityDescription"),
    ("homeassistant.components.select", "SelectEntityDescription"),
    ("homeassistant.components.sensor", "SensorEntityDescription"),
    ("homeassistant.components.button", "ButtonEntityDescription"),
    ("homeassistant.components.switch", "SwitchEntityDescription"),
    ("homeassistant.components.time", "TimeEntityDescription"),
]:
    setattr(sys.modules[module_key], class_name, StubEntityDescription)

# Make ``homeassistant.util.dt.now()`` behave like the real helper so date /
# timezone-dependent code under test can call ``.date().isoformat()`` on it.
# Stitch the parent attribute too: ``from homeassistant.util import dt as
# dt_util`` resolves through the parent's attribute, not via sys.modules.
import datetime as _datetime  # noqa: E402

_dt_module = sys.modules["homeassistant.util.dt"]
_dt_module.now = lambda: _datetime.datetime.now()
sys.modules["homeassistant.util"].dt = _dt_module


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
