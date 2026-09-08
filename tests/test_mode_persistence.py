"""Tests for mode select state persistence across Home Assistant restarts.

Covers behaviour added for Issue #111 / #122:

- ``_load_mode_state_into`` restores stored mode (1=normal, 2=smart) at setup.
- ``_reconcile_mode_into`` preserves cached mode when raw mode is 0 and saves mode changes.
- Storage exceptions or corrupt values are safely handled without breaking setup/polling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.ble_client import PetkitFountainData
from custom_components.petkit_ble.const import ALIAS_CTW3, ALIAS_W5, MODE_NORMAL, MODE_SMART
from custom_components.petkit_ble.coordinator import (
    _load_mode_state_into,
    _reconcile_mode_into,
    _save_mode_state_into,
)
from custom_components.petkit_ble.number import NUMBER_DESCRIPTIONS


def _make_store() -> MagicMock:
    """Build a Store mock whose async methods are awaitable."""
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store


class TestModeLoadPersistence:
    """Test loading mode state from Store."""

    @pytest.mark.asyncio
    async def test_load_restores_valid_normal_mode(self) -> None:
        store = _make_store()
        store.async_load = AsyncMock(return_value={"mode": MODE_NORMAL})

        mode = await _load_mode_state_into(store)
        assert mode == MODE_NORMAL

    @pytest.mark.asyncio
    async def test_load_restores_valid_smart_mode(self) -> None:
        store = _make_store()
        store.async_load = AsyncMock(return_value={"mode": MODE_SMART})

        mode = await _load_mode_state_into(store)
        assert mode == MODE_SMART

    @pytest.mark.asyncio
    async def test_load_handles_missing_store(self) -> None:
        store = _make_store()
        store.async_load = AsyncMock(return_value=None)

        mode = await _load_mode_state_into(store)
        assert mode is None

    @pytest.mark.asyncio
    async def test_load_handles_invalid_mode_value(self) -> None:
        store = _make_store()
        store.async_load = AsyncMock(return_value={"mode": 99})

        mode = await _load_mode_state_into(store)
        assert mode is None

    @pytest.mark.asyncio
    async def test_load_handles_corrupt_store(self) -> None:
        store = _make_store()
        store.async_load = AsyncMock(return_value={"mode": "invalid"})

        mode = await _load_mode_state_into(store)
        assert mode is None

    @pytest.mark.asyncio
    async def test_load_swallows_exceptions(self) -> None:
        store = _make_store()
        store.async_load = AsyncMock(side_effect=RuntimeError("disk failure"))

        mode = await _load_mode_state_into(store)
        assert mode is None


class TestModeReconciliationAndSave:
    """Test mode reconciliation and scheduling delayed save."""

    def test_reconcile_applies_data_mode_and_saves_when_new(self) -> None:
        store = _make_store()
        data = PetkitFountainData(alias=ALIAS_CTW3, mode=MODE_SMART)

        new_mode = _reconcile_mode_into(data, cached_mode=None, store=store)
        assert new_mode == MODE_SMART
        assert data.mode == MODE_SMART
        store.async_delay_save.assert_called_once()

    def test_reconcile_retains_cached_mode_when_data_mode_is_zero(self) -> None:
        store = _make_store()
        # Initial poll returns mode=0 because pump is off/sleeping
        data = PetkitFountainData(alias=ALIAS_CTW3, mode=0)

        new_mode = _reconcile_mode_into(data, cached_mode=MODE_NORMAL, store=store)
        assert new_mode == MODE_NORMAL
        assert data.mode == MODE_NORMAL
        # Mode did not change from cached_mode so store save is not called again
        store.async_delay_save.assert_not_called()

    def test_reconcile_handles_store_save_exception(self) -> None:
        store = _make_store()
        store.async_delay_save.side_effect = RuntimeError("disk full")
        data = PetkitFountainData(alias=ALIAS_CTW3, mode=MODE_NORMAL)

        # Must not raise exception
        new_mode = _reconcile_mode_into(data, cached_mode=None, store=store)
        assert new_mode == MODE_NORMAL


@pytest.mark.asyncio
async def test_save_mode_state_into_schedules_save() -> None:
    store = _make_store()
    _save_mode_state_into(store, MODE_SMART)

    store.async_delay_save.assert_called_once()
    save_func = store.async_delay_save.call_args[0][0]
    assert save_func() == {"mode": MODE_SMART}


@pytest.mark.asyncio
async def test_led_brightness_max_value_ctw3_vs_generic() -> None:
    desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == "led_brightness")
    ctw3_data = PetkitFountainData(alias=ALIAS_CTW3)
    w5_data = PetkitFountainData(alias=ALIAS_W5)

    assert desc.max_value_fn(ctw3_data) == 3.0
    assert desc.max_value_fn(w5_data) == 10.0
    assert desc.max_value_fn(w5_data) == 10.0
