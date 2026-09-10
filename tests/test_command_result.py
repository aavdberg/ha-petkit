"""Tests for command success/failure reporting."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.petkit_ble.ble_client import PetkitBleClient
from custom_components.petkit_ble.const import ALIAS_W5, CMD_SET_POWER_MODE


def _run_send_command(response: bytes | None) -> tuple[bool, AsyncMock]:
    """Run a command with BLE transport methods mocked out."""
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    client = PetkitBleClient(device)
    disconnect = AsyncMock()

    with (
        patch.object(client, "_connect", new=AsyncMock()),
        patch.object(client, "_authenticate", new=AsyncMock()),
        patch.object(client, "_send_and_wait", new=AsyncMock(return_value=response)),
        patch.object(client, "disconnect", new=disconnect),
    ):
        result = asyncio.run(client.async_send_command(CMD_SET_POWER_MODE, [1, 0], ALIAS_W5))

    return result, disconnect


def test_command_timeout_returns_false() -> None:
    """A command with no matching response must not be reported as successful."""
    result, disconnect = _run_send_command(None)

    assert result is False
    disconnect.assert_awaited_once()


def test_command_response_returns_true() -> None:
    """A received response continues to report command success."""
    result, disconnect = _run_send_command(b"\x01")

    assert result is True
    disconnect.assert_awaited_once()


def test_empty_response_payload_is_still_a_response() -> None:
    """An empty payload is distinct from a timeout and remains successful."""
    result, disconnect = _run_send_command(b"")

    assert result is True
    disconnect.assert_awaited_once()
