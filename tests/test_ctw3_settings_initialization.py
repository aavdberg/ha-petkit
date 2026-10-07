"""Tests for explicitly initializing unread CTW3 settings."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.ble_client import PetkitFountainData
from custom_components.petkit_ble.const import ALIAS_CTW3, CMD_WRITE_SETTINGS
from custom_components.petkit_ble.coordinator import _SETTINGS_FIELDS, PetkitBleCoordinator
from custom_components.petkit_ble.protocol import build_settings_payload_ctw3


@pytest.mark.asyncio
async def test_initialize_ctw3_settings_writes_defaults_and_caches_them() -> None:
    coordinator = MagicMock()
    coordinator.data = PetkitFountainData(alias=ALIAS_CTW3)
    coordinator.data.smart_inductive_switch = None
    coordinator.data.battery_inductive_switch = None
    coordinator._settings_cache = {}
    coordinator.async_send_command = AsyncMock(return_value=True)
    coordinator.async_set_updated_data = MagicMock()
    coordinator.async_request_refresh = AsyncMock()

    await PetkitBleCoordinator.async_initialize_ctw3_settings(coordinator)

    expected_payload = build_settings_payload_ctw3(
        smart_work=0,
        smart_sleep=0,
        battery_work_time=0,
        battery_sleep_time=0,
        led_switch=0,
        led_brightness=1,
        dnd_enabled=0,
        child_lock=0,
        smart_inductive_switch=0,
        battery_inductive_switch=0,
    )
    coordinator.async_send_command.assert_awaited_once_with(CMD_WRITE_SETTINGS, expected_payload)
    assert coordinator.data.smart_inductive_switch == 0
    assert coordinator.data.battery_inductive_switch == 0
    assert coordinator.data.config_loaded is True
    assert all(field in coordinator._settings_cache for field in _SETTINGS_FIELDS)
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.data)
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_ctw3_settings_initialization_does_not_cache_values() -> None:
    coordinator = MagicMock()
    coordinator.data = PetkitFountainData(alias=ALIAS_CTW3)
    coordinator.data.smart_inductive_switch = None
    coordinator.data.battery_inductive_switch = None
    coordinator._settings_cache = {}
    coordinator.async_send_command = AsyncMock(return_value=False)
    coordinator.async_set_updated_data = MagicMock()
    coordinator.async_request_refresh = AsyncMock()

    await PetkitBleCoordinator.async_initialize_ctw3_settings(coordinator)

    assert coordinator._settings_cache == {}
    assert coordinator.data.smart_inductive_switch is None
    assert coordinator.data.battery_inductive_switch is None
    coordinator.async_set_updated_data.assert_not_called()
    coordinator.async_request_refresh.assert_not_awaited()
