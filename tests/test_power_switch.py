"""Tests for the CTW3 power switch payload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.const import CMD_SET_POWER_MODE
from custom_components.petkit_ble.switch import PetkitPowerSwitch


def _switch(mode: int) -> PetkitPowerSwitch:
    switch = object.__new__(PetkitPowerSwitch)
    switch.coordinator = MagicMock()
    switch.coordinator.data = SimpleNamespace(is_ctw3=True, mode=mode)
    switch.coordinator.async_send_command = AsyncMock(return_value=True)
    switch.coordinator.async_request_refresh = AsyncMock()
    return switch


@pytest.mark.parametrize(
    ("mode", "power", "expected"),
    [
        (1, 1, [1, 1, 1]),
        (2, 1, [1, 1, 2]),
        (1, 0, [0, 0, 1]),
        (2, 0, [0, 0, 2]),
    ],
)
async def test_ctw3_power_payload(mode: int, power: int, expected: list[int]) -> None:
    """Turning on keeps the pump running in both modes; turning off sends suspend=0."""
    switch = _switch(mode)
    await switch._set_power(power)
    switch.coordinator.async_send_command.assert_awaited_once_with(CMD_SET_POWER_MODE, expected)
