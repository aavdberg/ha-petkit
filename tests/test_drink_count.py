"""Tests for the daily drink-event counter and its persistence.

Covers behaviour added in fix/ctw3-drink-events-counter:

- ``_track_drink_event_into`` increments only on a ``detect_status`` 0 → 1
  edge.
- The counter resets to 0 when the local date rolls over.
- The counter is persisted to ``Store`` and restored at startup, so a Home
  Assistant restart no longer wipes today's count.
- A persisted count from a previous day is dropped on load.
- A negative count from a corrupt store is rejected.

Tests target the free functions ``_track_drink_event_into`` and
``_load_drink_state_into`` so the full ``DataUpdateCoordinator`` chain
does not need to be mocked (it inherits from a stubbed-out class and
cannot be safely instantiated in tests).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.ble_client import PetkitFountainData
from custom_components.petkit_ble.const import ALIAS_CTW3
from custom_components.petkit_ble.coordinator import (
    _DrinkCountState,
    _load_drink_state_into,
    _track_drink_event_into,
)


def _make_store() -> MagicMock:
    """Build a Store mock whose async methods are awaitable."""
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store


@pytest.fixture
def today_iso() -> str:
    """Capture today's ISO date once per test to avoid midnight-rollover flakes."""
    return date.today().isoformat()


class TestEdgeDetection:
    """Counter increments on a 0 → 1 detect_status transition only."""

    @pytest.mark.asyncio
    async def test_zero_to_one_increments_and_persists(self, today_iso: str) -> None:
        state = _DrinkCountState(prev_detect_status=0, date_iso=today_iso)
        store = _make_store()

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=1)
        await _track_drink_event_into(state, store, data)

        assert state.count == 1
        assert data.drink_event_count == 1
        store.async_save.assert_awaited_once_with({"count": 1, "date": today_iso})

    @pytest.mark.asyncio
    async def test_steady_one_does_not_increment(self, today_iso: str) -> None:
        state = _DrinkCountState(prev_detect_status=1, date_iso=today_iso)
        store = _make_store()

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=1)
        await _track_drink_event_into(state, store, data)

        assert state.count == 0
        store.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_one_to_zero_does_not_increment(self, today_iso: str) -> None:
        state = _DrinkCountState(prev_detect_status=1, date_iso=today_iso)
        store = _make_store()

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=0)
        await _track_drink_event_into(state, store, data)

        assert state.count == 0

    @pytest.mark.asyncio
    async def test_first_poll_initialises_without_counting(self, today_iso: str) -> None:
        """A fresh state with prev=None must not count even if detect=1."""
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        assert state.prev_detect_status is None

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=1)
        await _track_drink_event_into(state, store, data)

        assert state.count == 0
        assert state.prev_detect_status == 1


class TestDailyReset:
    """Counter resets when the local date rolls over."""

    @pytest.mark.asyncio
    async def test_rollover_resets_counter(self, today_iso: str) -> None:
        state = _DrinkCountState(prev_detect_status=0, count=7, date_iso="2000-01-01")
        store = _make_store()

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=0)
        await _track_drink_event_into(state, store, data)

        assert state.date_iso == today_iso
        assert state.count == 0
        assert data.drink_event_count == 0

    @pytest.mark.asyncio
    async def test_same_day_keeps_counter(self, today_iso: str) -> None:
        state = _DrinkCountState(prev_detect_status=0, count=3, date_iso=today_iso)
        store = _make_store()

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=0)
        await _track_drink_event_into(state, store, data)

        assert state.count == 3
        assert data.drink_event_count == 3


class TestPersistence:
    """Counter survives a Home Assistant restart via the Store helper."""

    @pytest.mark.asyncio
    async def test_load_restores_today_count(self, today_iso: str) -> None:
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        store.async_load = AsyncMock(return_value={"count": 12, "date": today_iso})

        await _load_drink_state_into(state, store)

        assert state.count == 12
        assert state.date_iso == today_iso

    @pytest.mark.asyncio
    async def test_load_drops_stale_count_from_previous_day(self, today_iso: str) -> None:
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        store.async_load = AsyncMock(return_value={"count": 99, "date": "2000-01-01"})

        await _load_drink_state_into(state, store)

        assert state.count == 0
        assert state.date_iso == today_iso

    @pytest.mark.asyncio
    async def test_load_handles_missing_store(self, today_iso: str) -> None:
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        store.async_load = AsyncMock(return_value=None)

        await _load_drink_state_into(state, store)

        assert state.count == 0

    @pytest.mark.asyncio
    async def test_load_handles_corrupt_store(self, today_iso: str) -> None:
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        store.async_load = AsyncMock(return_value={"count": "not-an-int", "date": None})

        await _load_drink_state_into(state, store)

        assert state.count == 0

    @pytest.mark.asyncio
    async def test_load_discards_negative_count(self, today_iso: str) -> None:
        """A negative count from a corrupt store must not surface to the sensor."""
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        store.async_load = AsyncMock(return_value={"count": -5, "date": today_iso})

        await _load_drink_state_into(state, store)

        assert state.count == 0

    @pytest.mark.asyncio
    async def test_load_swallows_storage_exceptions(self, today_iso: str) -> None:
        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()
        store.async_load = AsyncMock(side_effect=RuntimeError("disk full"))

        # Must not raise — storage failures should never block setup.
        await _load_drink_state_into(state, store)
        assert state.count == 0

    @pytest.mark.asyncio
    async def test_save_failure_does_not_break_polling(self, today_iso: str) -> None:
        state = _DrinkCountState(prev_detect_status=0, date_iso=today_iso)
        store = _make_store()
        store.async_save = AsyncMock(side_effect=RuntimeError("disk full"))

        data = PetkitFountainData(alias=ALIAS_CTW3, detect_status=1)
        # Must not raise — storage failures must not break the poll loop.
        await _track_drink_event_into(state, store, data)
        assert state.count == 1


class TestParserToCounterEndToEnd:
    """Parser + counter together must increment on real CTW3 fw 111 frames.

    Regression test for issue #65. The captured log
    ``Logs/home-assistant_petkit_ble_2026-05-01T12-01-29.952Z.log`` contains
    a real drink event at 13:59 where byte 19 transitions ``0x00 -> 0x02 ->
    0x00``. Before the parser was fixed to normalise non-zero bytes to 1,
    the counter never saw a strict 0 → 1 edge and therefore never
    incremented.
    """

    # Three real 30-byte CTW3 CMD 210 payloads from the captured log:
    # 13:58:00 (idle, byte19=0x00) → 13:59:08 (cat drinks, byte19=0x02) →
    # 14:00:17 (cat leaves, byte19=0x00).
    IDLE_BEFORE = bytes.fromhex("010101020000000000002470a507010000b35b00141a10736400c506c306")
    DETECTED = bytes.fromhex("010101020000000000002470e907010000b39f02141a10766400c5068508")
    IDLE_AFTER = bytes.fromhex("0101010200000000000024702f07010000b3e500141410736400c506c706")

    @pytest.mark.asyncio
    async def test_real_drink_event_increments_counter(self, today_iso: str) -> None:
        """Feed three real frames through parser+counter; expect count=1."""
        from custom_components.petkit_ble.ble_client import PetkitBleClient

        # Sanity: the captured frames really do flip byte 19 the way we think.
        assert self.IDLE_BEFORE[19] == 0x00
        assert self.DETECTED[19] == 0x02
        assert self.IDLE_AFTER[19] == 0x00

        state = _DrinkCountState(date_iso=today_iso)
        store = _make_store()

        for raw in (self.IDLE_BEFORE, self.DETECTED, self.IDLE_AFTER):
            data = PetkitFountainData(alias=ALIAS_CTW3)
            PetkitBleClient._parse_state_ctw3(data, raw)
            await _track_drink_event_into(state, store, data)

        assert state.count == 1, (
            "One drink event observed → counter must read 1; regression for issue #65 (CTW3 fw 111 emits 0x02 not 0x01)"
        )
