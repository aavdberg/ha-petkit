"""Tests for the CMD 210 byte-diff diagnostic helper."""

from __future__ import annotations

from custom_components.petkit_ble.coordinator import _diff_state_bytes


class TestDiffStateBytes:
    """Tests for the byte-diff helper used by the diagnostic poll log."""

    def test_returns_empty_when_prev_is_empty(self) -> None:
        """Initial poll has no previous frame to diff against."""
        assert _diff_state_bytes(b"", b"\x01\x02") == []

    def test_returns_empty_when_payloads_identical(self) -> None:
        """No bytes changed → empty diff."""
        payload = bytes.fromhex("01020304")
        assert _diff_state_bytes(payload, payload) == []

    def test_reports_changed_byte_with_old_and_new(self) -> None:
        """Each diff entry is (index, old, new)."""
        prev = bytes.fromhex("0008072307")
        curr = bytes.fromhex("c506be0607")
        # Indices 0..3 differ; index 4 is the same.
        assert _diff_state_bytes(prev, curr) == [
            (0, 0x00, 0xC5),
            (1, 0x08, 0x06),
            (2, 0x07, 0xBE),
            (3, 0x23, 0x06),
        ]

    def test_skips_noisy_byte_indices(self) -> None:
        """Bytes 9..18 (CTW3 uptime tick) are excluded from the diff."""
        prev = bytearray(30)
        curr = bytearray(30)
        # Change bytes inside the noisy window — must NOT appear.
        prev[10] = 0x01
        curr[10] = 0xFF
        prev[18] = 0x00
        curr[18] = 0x42
        # Change a byte outside the noisy window — MUST appear.
        prev[26] = 0x08
        curr[26] = 0xC5
        diff = _diff_state_bytes(bytes(prev), bytes(curr))
        assert diff == [(26, 0x08, 0xC5)]

    def test_real_ctw3_frame_pair_highlights_byte_26(self) -> None:
        """Real captured frames before/after a drink event.

        Frames sourced from
        ``Logs/home-assistant_petkit_ble_2026-05-01T10-15-53.221Z.log``.
        With the noisy uptime bytes (9..18) suppressed, byte 26 jumping
        from 0x08 to 0xc5 stands out as the strongest pet-detection
        candidate (see plan.md / issue #65).
        """
        prev = bytes.fromhex("01010102000000000000242bfe080100006fb40014171076640008072307")
        curr = bytes.fromhex("01010102000000000000245787080100009b3d00141a10736400c506be06")
        diff = _diff_state_bytes(prev, curr)
        # Diff must include byte 26 (0x08 -> 0xc5).
        assert (26, 0x08, 0xC5) in diff
        # And must exclude every byte inside the noisy uptime window.
        assert all(i not in range(9, 19) for i, _, _ in diff)
