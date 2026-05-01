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
        # not exceed the smallest observed CTW3 payload, otherwise valid CTW3
        # frames would be misclassified as generic.
        assert CTW3_STATE_PAYLOAD_MIN_LEN <= 26

    def test_threshold_matches_ctw3_parser_minimum(self) -> None:
        # The CTW3 parser requires at least 26 bytes; inferring CTW3 from a
        # shorter payload would persist the alias and then immediately fail to
        # parse. Keep the discriminator aligned with the parser minimum.
        assert CTW3_STATE_PAYLOAD_MIN_LEN == 26


class TestCtw3SelfHealInference:
    """Cover the alias self-heal branch in PetkitBleClient.async_poll.

    async_poll itself requires a connected BleakClient, but the self-heal
    decision is a pure check on (data.alias, len(payload_210)). Exercise the
    same condition + parser dispatch the live code uses, to lock in the
    behaviour: an unknown stored alias plus a CTW3-sized payload must (a)
    select the CTW3 parser and (b) yield the expected CTW3 fields.
    """

    def test_mac_alias_with_ctw3_payload_uses_ctw3_parser(self, sample_ctw3_state_payload: bytes) -> None:
        from custom_components.petkit_ble.ble_client import (
            PetkitBleClient,
            PetkitFountainData,
        )
        from custom_components.petkit_ble.const import CTW3_ALIASES

        data = PetkitFountainData(alias="A4:C1:38:E6:2B:1C")

        # Mirror the live self-heal condition in async_poll.
        if data.alias not in KNOWN_ALIASES and len(sample_ctw3_state_payload) >= CTW3_STATE_PAYLOAD_MIN_LEN:
            data.alias = ALIAS_CTW3

        assert data.alias == ALIAS_CTW3
        assert data.alias in CTW3_ALIASES

        PetkitBleClient._parse_state_ctw3(data, sample_ctw3_state_payload)

        # Spot-check fields that only the CTW3 parser populates correctly.
        assert data.power_status == 1
        assert data.suspend_status == 0
        assert data.mode == 2
        assert data.electric_status == 2
        assert data.battery_percent == 85

    def test_short_payload_does_not_trigger_inference(self) -> None:
        # An 18-byte generic payload must NOT cause CTW3 inference, even
        # though the stored alias is unknown.
        from custom_components.petkit_ble.ble_client import PetkitFountainData

        data = PetkitFountainData(alias="A4:C1:38:E6:2B:1C")
        payload = bytes(18)

        triggered = data.alias not in KNOWN_ALIASES and len(payload) >= CTW3_STATE_PAYLOAD_MIN_LEN

        assert triggered is False
