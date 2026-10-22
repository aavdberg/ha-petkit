# UV-C Protocol Findings from PETKIT APK 13.10.1

## Verified findings

- The APK's `CTW3DataConvertor` parses CMD 210 payload byte 25 into `moduleStatus`. The inspected client code does not interpret the field's bits as UV-C state.
- CTW3 CMD 221 writers serialize a 12-byte settings payload containing smart/battery schedules, LED settings, DND, child lock, and detection flags. No UV-C field or dedicated UV-C BLE command was found in the inspected converter.
- The APK identifies W4XUVC as W5 type code 6. Its `W5DataConvertor` uses the generic CMD 210 state layout and contains no W4XUVC-specific UV-C status or control handling.
- The integration's existing CTW3 `uvc_active` sensor interprets `module_status & 0x01` as active. This APK confirms the byte offset but does not confirm that bit's meaning.
- The APK includes W4XUVC and sterilization UI/model strings, but those names alone do not establish a BLE status mapping or control payload.

## Safe implementation scope

- Keep the existing integration behavior unchanged; do not enable `uvc_active` for W4XUVC or add UV-C write entities based on unverified protocol assumptions.
- Document the APK evidence and the remaining protocol gaps. A BLE capture or another authoritative protocol source is required before adding or changing UV-C status/control behavior.
- Keep this change related to, but do not auto-close, tracking issue #148, which still covers unrelated unfinished work.

## Validation

- Static inspection of the user-provided APK was performed locally. The APK and decompiled output are not part of this repository.
- This is a documentation-only change; no integration tests or runtime behavior are changed.
