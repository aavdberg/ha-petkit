"""Tests for explicitly initializing unread CTW3 settings."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.ble_client import PetkitFountainData
from custom_components.petkit_ble.const import ALIAS_CTW3, CMD_WRITE_SETTINGS
from custom_components.petkit_ble.coordinator import (
    _SETTINGS_FIELDS,
    PetkitBleCoordinator,
    _load_settings_cache_into,
    _reconcile_settings_into,
)
from custom_components.petkit_ble.protocol import build_settings_payload_ctw3


class _MemorySettingsStore:
    """Minimal Store stub for settings persistence tests."""

    def __init__(self) -> None:
        self.snapshot: dict[str, int] | None = None
        self.save_callback: Callable[[], dict[str, int]] | None = None

    async def async_load(self) -> dict[str, int] | None:
        return self.snapshot

    def async_delay_save(self, callback: Callable[[], dict[str, int]], _delay: float) -> None:
        self.save_callback = callback

    def flush(self) -> None:
        assert self.save_callback is not None
        self.snapshot = self.save_callback()


def _make_coordinator(*, send_success: bool = True) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = PetkitFountainData(alias=ALIAS_CTW3)
    coordinator.data.smart_inductive_switch = None
    coordinator.data.battery_inductive_switch = None
    coordinator._ble_lock = asyncio.Lock()
    coordinator._name = "fountain"
    coordinator._settings_cache = {}
    coordinator._settings_store = _MemorySettingsStore()
    coordinator._schedule_settings_save = lambda: PetkitBleCoordinator._schedule_settings_save(coordinator)
    coordinator._async_send_command_locked = AsyncMock(return_value=send_success)
    coordinator.async_set_updated_data = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_initialize_ctw3_settings_writes_defaults_and_caches_them() -> None:
    coordinator = _make_coordinator()

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
    coordinator._async_send_command_locked.assert_awaited_once_with(CMD_WRITE_SETTINGS, expected_payload)
    assert coordinator.data.smart_inductive_switch == 0
    assert coordinator.data.battery_inductive_switch == 0
    assert coordinator.data.config_loaded is True
    assert all(field in coordinator._settings_cache for field in _SETTINGS_FIELDS)
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.data)
    coordinator.async_request_refresh.assert_awaited_once()
    assert coordinator._ble_lock.locked() is False


@pytest.mark.asyncio
async def test_failed_ctw3_settings_initialization_does_not_cache_values() -> None:
    coordinator = _make_coordinator(send_success=False)

    await PetkitBleCoordinator.async_initialize_ctw3_settings(coordinator)

    coordinator._async_send_command_locked.assert_awaited_once()
    assert coordinator._settings_cache == {}
    assert coordinator.data.smart_inductive_switch is None
    assert coordinator.data.battery_inductive_switch is None
    coordinator.async_set_updated_data.assert_not_called()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_initialization_uses_settings_reconciled_during_poll() -> None:
    coordinator = _make_coordinator()
    coordinator._settings_cache.update(
        smart_inductive_switch=1,
        battery_inductive_switch=0,
        smart_time_on=15,
    )

    await PetkitBleCoordinator.async_initialize_ctw3_settings(coordinator)

    coordinator._async_send_command_locked.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_initialized_settings_and_later_changes_survive_reload() -> None:
    coordinator = _make_coordinator()

    await PetkitBleCoordinator.async_initialize_ctw3_settings(coordinator)
    coordinator._settings_store.flush()

    PetkitBleCoordinator.apply_setting_optimistic(coordinator, "smart_time_on", 20)
    coordinator._settings_store.flush()

    restored_cache: dict[str, int] = {}
    await _load_settings_cache_into(restored_cache, coordinator._settings_store)
    fresh_data = PetkitFountainData(alias=ALIAS_CTW3)
    _reconcile_settings_into(fresh_data, restored_cache, warned=False, name="fountain", address="address")

    assert restored_cache["smart_time_on"] == 20
    assert fresh_data.smart_time_on == 20
    assert fresh_data.smart_inductive_switch == 0
    assert fresh_data.battery_inductive_switch == 0
    assert fresh_data.config_loaded is True


@pytest.mark.asyncio
async def test_corrupt_persisted_settings_are_discarded() -> None:
    store = _MemorySettingsStore()
    store.snapshot = {
        "smart_inductive_switch": True,
        "battery_inductive_switch": 1,
        "smart_time_on": -1,
        "led_switch": 256,
    }
    cache: dict[str, int] = {}

    await _load_settings_cache_into(cache, store)

    assert cache == {"battery_inductive_switch": 1}
