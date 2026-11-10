"""Tests for the power switch payload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.petkit_ble.const import CMD_SET_POWER_MODE
from custom_components.petkit_ble.switch import PetkitPowerSwitch


def _switch(mode: int, is_ctw3: bool = True) -> PetkitPowerSwitch:
    switch = object.__new__(PetkitPowerSwitch)
    switch.coordinator = MagicMock()
    switch.coordinator.data = SimpleNamespace(is_ctw3=is_ctw3, mode=mode)
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


@pytest.mark.parametrize(
    ("mode", "power", "expected"),
    [
        (1, 1, [1, 1]),
        (2, 1, [1, 2]),
        (1, 0, [0, 1]),
        (2, 0, [0, 2]),
        (0, 1, [1, 1]),
        (0, 0, [0, 1]),
    ],
)
async def test_generic_power_payload(mode: int, power: int, expected: list[int]) -> None:
    """Non-CTW3 power commands use [power, mode], keeping Normal and Smart distinct."""
    switch = _switch(mode, is_ctw3=False)
    await switch._set_power(power)
    switch.coordinator.async_send_command.assert_awaited_once_with(CMD_SET_POWER_MODE, expected)
