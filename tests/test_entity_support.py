"""Tests for entity support filtering per device model (Issue #118)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.petkit_ble.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
)
from custom_components.petkit_ble.ble_client import PetkitFountainData
from custom_components.petkit_ble.const import (
    ALIAS_CTW3,
    ALIAS_W4X,
    ALIAS_W4XUVC,
    CONF_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
)
from custom_components.petkit_ble.number import NUMBER_DESCRIPTIONS
from custom_components.petkit_ble.sensor import SENSOR_DESCRIPTIONS
from custom_components.petkit_ble.sensor import async_setup_entry as async_setup_sensor
from custom_components.petkit_ble.time import TIME_DESCRIPTIONS


@pytest.mark.asyncio
async def test_w4x_entity_setup() -> None:
    """Verify that W4X setup filters out unsupported entities (Issue #118)."""
    data = PetkitFountainData(alias=ALIAS_W4X)

    # Sensors
    supported_sensors = [d.key for d in SENSOR_DESCRIPTIONS if d.supported_fn(data)]
    assert "battery_percent" not in supported_sensors
    assert "battery_voltage_mv" not in supported_sensors
    assert "drink_count" not in supported_sensors
    assert "state_tail_hex" not in supported_sensors
    assert "filter_percent" in supported_sensors

    # Binary sensors
    supported_binary = [d.key for d in BINARY_SENSOR_DESCRIPTIONS if d.supported_fn(data)]
    assert "pet_detected" not in supported_binary
    assert "on_ac_power" not in supported_binary
    assert "low_battery" not in supported_binary
    assert "suspended" not in supported_binary
    assert "uvc_active" not in supported_binary
    assert "pump_running" in supported_binary

    # Numbers
    supported_numbers = [d.key for d in NUMBER_DESCRIPTIONS if d.supported_fn(data)]
    assert "battery_work_seconds" not in supported_numbers
    assert "battery_sleep_seconds" not in supported_numbers
    assert "smart_work_minutes" in supported_numbers

    # Times
    supported_times = [d.key for d in TIME_DESCRIPTIONS if d.supported_fn(data)]
    assert "led_on_time" in supported_times


@pytest.mark.asyncio
async def test_w4xuvc_entity_setup() -> None:
    """Verify that W4XUVC setup excludes battery/CTW3 entities."""
    data = PetkitFountainData(alias=ALIAS_W4XUVC)

    supported_binary = [d.key for d in BINARY_SENSOR_DESCRIPTIONS if d.supported_fn(data)]
    assert "uvc_active" not in supported_binary
    assert "pet_detected" not in supported_binary
    assert "on_ac_power" not in supported_binary
    assert "low_battery" not in supported_binary


@pytest.mark.asyncio
async def test_ctw3_entity_setup() -> None:
    """Verify that CTW3 setup includes battery, UVC, pet detection, but excludes unsupported times."""
    data = PetkitFountainData(alias=ALIAS_CTW3)

    supported_sensors = [d.key for d in SENSOR_DESCRIPTIONS if d.supported_fn(data)]
    assert "battery_percent" in supported_sensors
    assert "drink_count" in supported_sensors

    supported_binary = [d.key for d in BINARY_SENSOR_DESCRIPTIONS if d.supported_fn(data)]
    assert "pet_detected" in supported_binary
    assert "on_ac_power" in supported_binary
    assert "uvc_active" in supported_binary

    supported_numbers = [d.key for d in NUMBER_DESCRIPTIONS if d.supported_fn(data)]
    assert "battery_work_seconds" in supported_numbers

    supported_times = [d.key for d in TIME_DESCRIPTIONS if d.supported_fn(data)]
    assert len(supported_times) == 0


@pytest.mark.asyncio
async def test_async_setup_entry_w4x() -> None:
    """Test async_setup_entry for W4X to confirm entities added to HA."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.data = {CONF_MODEL: ALIAS_W4X, CONF_ADDRESS: "AA:BB:CC:DD:EE:FF", CONF_NAME: "Petkit_W4X"}

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.config_entry = config_entry
    coordinator.data = PetkitFountainData(alias=ALIAS_W4X)
    config_entry.runtime_data = coordinator

    added_sensors = []

    def mock_add_entities(entities):
        added_sensors.extend(entities)

    await async_setup_sensor(hass, config_entry, mock_add_entities)
    added_keys = [e.entity_description.key for e in added_sensors]
    assert "battery_percent" not in added_keys
    assert "drink_count" not in added_keys
    assert "filter_percent" in added_keys
