"""Tests for alias detection and self-heal logic."""

from __future__ import annotations

from custom_components.petkit_ble.config_flow import _get_alias_from_name
from custom_components.petkit_ble.const import (
    ALIAS_CTW2,
    ALIAS_CTW3,
    ALIAS_W4X,
    ALIAS_W4XUVC,
    ALIAS_W5,
    ALIAS_W5C,
    ALIAS_W5N,
    CTW3_STATE_PAYLOAD_MIN_LEN,
    KNOWN_ALIASES,
)


class TestGetAliasFromName:
    """Tests for _get_alias_from_name."""

    def test_ctw3_name(self) -> None:
        assert _get_alias_from_name("Petkit_CTW3_100") == ALIAS_CTW3

    def test_ctw2_name(self) -> None:
        assert _get_alias_from_name("Petkit_CTW2_42") == ALIAS_CTW2

    def test_w5c_before_w5(self) -> None:
        # Order matters: W5C must be matched before the generic W5 fallback.
        assert _get_alias_from_name("Petkit_W5C_01") == ALIAS_W5C

    def test_w5n_before_w5(self) -> None:
        assert _get_alias_from_name("Petkit_W5N_01") == ALIAS_W5N

    def test_w4xuvc_before_w4x(self) -> None:
        assert _get_alias_from_name("Petkit_W4XUVC_99") == ALIAS_W4XUVC

    def test_w4x(self) -> None:
        assert _get_alias_from_name("Petkit_W4X_01") == ALIAS_W4X

    def test_w5_generic(self) -> None:
        assert _get_alias_from_name("Petkit_W5_01") == ALIAS_W5

    def test_mac_returns_empty(self) -> None:
        """MAC-as-name must not be echoed as the alias.

        Regression test for the alias-self-heal bug: when the BLE local name
        was unavailable at config-flow time (common with proxy adverts) the
        old code returned the raw input — typically the MAC — as the alias,
        which then poisoned all downstream model-specific behaviour.
        """
        assert _get_alias_from_name("A4:C1:38:E6:2B:1C") == ""

    def test_empty_returns_empty(self) -> None:
        assert _get_alias_from_name("") == ""

    def test_unknown_token_returns_empty(self) -> None:
        assert _get_alias_from_name("SomeOtherDevice") == ""


class TestKnownAliases:
    """Sanity checks for the KNOWN_ALIASES set."""

    def test_contains_all_aliases(self) -> None:
        assert ALIAS_CTW3 in KNOWN_ALIASES
        assert ALIAS_CTW2 in KNOWN_ALIASES
        assert ALIAS_W5C in KNOWN_ALIASES
        assert ALIAS_W5N in KNOWN_ALIASES
        assert ALIAS_W5 in KNOWN_ALIASES
        assert ALIAS_W4XUVC in KNOWN_ALIASES
        assert ALIAS_W4X in KNOWN_ALIASES

    def test_does_not_contain_mac_or_empty(self) -> None:
        assert "A4:C1:38:E6:2B:1C" not in KNOWN_ALIASES
        assert "" not in KNOWN_ALIASES


class TestStatePayloadLengthDiscriminator:
    """The CTW3 self-heal threshold must distinguish CTW3 from generic."""

    def test_threshold_above_generic(self) -> None:
        # Generic CMD 210 payloads observed in the field are 12-18 bytes;
        # threshold must be strictly greater.
        assert CTW3_STATE_PAYLOAD_MIN_LEN > 18

    def test_threshold_at_or_below_ctw3(self) -> None:
        # CTW3 payloads observed in the field are 26-30 bytes; threshold must
        # not exceed the smallest observed CTW3 payload.
        assert CTW3_STATE_PAYLOAD_MIN_LEN <= 26
