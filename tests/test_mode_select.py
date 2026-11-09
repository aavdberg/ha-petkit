"""Tests for the mode select payload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.const import CMD_SET_POWER_MODE
from custom_components.petkit_ble.select import PetkitModeSelect


def _select() -> PetkitModeSelect:
    select = object.__new__(PetkitModeSelect)
    select.coordinator = MagicMock()
    select.coordinator.data = SimpleNamespace(is_ctw3=False, alias="CTW2")
    select.coordinator.async_send_command = AsyncMock(return_value=True)
    select.coordinator.async_request_refresh = AsyncMock()
    return select


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("normal", [1, 1]),
        ("smart", [1, 2]),
    ],
)
async def test_generic_mode_payload(option: str, expected: list[int]) -> None:
    """Selecting a mode on a non-CTW3 device powers on with the mode in byte 1."""
    select = _select()
    await select.async_select_option(option)
    select.coordinator.async_send_command.assert_awaited_once_with(CMD_SET_POWER_MODE, expected)
