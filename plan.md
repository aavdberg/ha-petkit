# UV-C Sterilisation Implementation Plan

## Findings

- `PetkitFountainData.has_uvc` identifies CTW3 and W4XUVC devices.
- CTW3 CMD 210 parsing exposes `module_status`; the existing `uvc_active` binary sensor reads bit 0 but is currently supported only on CTW3.
- W4XUVC status decoding and the BLE command/payload for UV-C control are not confirmed in the repository or tests.

## Proposed scope

1. Confirm UV-C status byte/bit mapping and the control command/payload for both supported device variants from verified APK or device evidence.
2. Use the confirmed protocol in the state model and command path; expose UVC status and control entities only on devices for which each behavior is confirmed.
3. Add focused protocol/entity tests and matching translations for all supported languages.
4. Run the targeted tests, Ruff checks, secret scanning, and required parallel validation.

## Approval gate

Do not implement or send UV-C write commands based on guessed protocol details. Proceed after the plan is approved and the missing protocol mappings are supplied or otherwise verified.
