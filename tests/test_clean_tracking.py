"""Tests for cleaning guidance tracking and persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.ble_client import PetkitFountainData
from custom_components.petkit_ble.const import ALIAS_CTW3
from custom_components.petkit_ble.coordinator import (
    _LastCleanedState,
    _apply_clean_state_into,
    _load_clean_state_into,
)


def _make_store() -> MagicMock:
    """Build a Store mock whose async methods are awaitable."""
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store


class TestCleanStateLoading:
    """State loading from Store snapshot."""

    @pytest.mark.anyio
    async def test_load_valid_timestamp(self) -> None:
        state = _LastCleanedState()
        store = _make_store()
        valid_iso = "2026-09-01T12:00:00+00:00"
        store.async_load = AsyncMock(return_value={"last_cleaned": valid_iso})

        await _load_clean_state_into(state, store)

        assert state.last_cleaned_iso == valid_iso
        store.async_save.assert_not_awaited()

    @pytest.mark.anyio
    async def test_load_missing_store_initializes_and_saves(self) -> None:
        state = _LastCleanedState()
        store = _make_store()
        store.async_load = AsyncMock(return_value=None)

        await _load_clean_state_into(state, store)

        assert state.last_cleaned_iso != ""
        store.async_save.assert_awaited_once()

    @pytest.mark.anyio
    async def test_load_corrupt_store_initializes_and_saves(self) -> None:
        state = _LastCleanedState()
        store = _make_store()
        store.async_load = AsyncMock(return_value={"last_cleaned": "invalid-date"})

        await _load_clean_state_into(state, store)

        assert state.last_cleaned_iso != ""
        store.async_save.assert_awaited_once()


class TestCleanStateCalculation:
    """Calculation of days_since_clean and last_cleaned."""

    def test_apply_clean_state_recent(self) -> None:
        data = PetkitFountainData(alias=ALIAS_CTW3)
        now_dt = datetime.now(timezone.utc)
        three_days_ago = (now_dt - timedelta(days=3, hours=2)).isoformat()
        state = _LastCleanedState(last_cleaned_iso=three_days_ago)

        _apply_clean_state_into(state, data)

        assert data.days_since_clean == 3
        assert isinstance(data.last_cleaned, datetime)

    def test_apply_clean_state_today(self) -> None:
        data = PetkitFountainData(alias=ALIAS_CTW3)
        now_dt = datetime.now(timezone.utc)
        two_hours_ago = (now_dt - timedelta(hours=2)).isoformat()
        state = _LastCleanedState(last_cleaned_iso=two_hours_ago)

        _apply_clean_state_into(state, data)

        assert data.days_since_clean == 0
        assert isinstance(data.last_cleaned, datetime)


class TestResetCleanAction:
    """Reset last cleaned timestamp action."""

    @pytest.mark.anyio
    async def test_reset_cleaned_updates_state_and_saves(self) -> None:
        state = _LastCleanedState(last_cleaned_iso="2026-08-01T00:00:00+00:00")
        store = _make_store()
        data = PetkitFountainData(alias=ALIAS_CTW3)

        now_iso = datetime.now(timezone.utc).isoformat()
        state.last_cleaned_iso = now_iso
        await store.async_save({"last_cleaned": now_iso})
        _apply_clean_state_into(state, data)

        assert data.days_since_clean == 0
        store.async_save.assert_awaited_once()
