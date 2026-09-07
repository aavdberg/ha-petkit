# Plan: Clean unsupported entities for W4X and other models (Issue #118)

## Context
Issue #118 reports that several entities are created for W4X devices that are not supported by the hardware (e.g. battery sensors, pet detection, UVC, suspended status, state tail). Because they are instantiated during `async_setup_entry`, Home Assistant registers them and displays them as permanently `Unavailable`.

## Proposed Changes

### 1. Add `supported_fn` to Entity Descriptions
Add a `supported_fn: Callable[[PetkitFountainData], bool] = lambda _: True` attribute to:
- `PetkitSensorEntityDescription` in `sensor.py`
- `PetkitBinarySensorDescription` in `binary_sensor.py`
- `PetkitNumberDescription` in `number.py`
- `PetkitTimeDescription` in `time.py`

### 2. Update Feature Definitions per Model
- `has_uvc`: Supported on `CTW3` and `W4XUVC` (`ALIAS_W4XUVC`).
- Battery entities (`battery_percent`, `battery_voltage_mv`, `low_battery`, `on_ac_power`, `battery_work_seconds`, `battery_sleep_seconds`): Supported on `CTW3` only.
- CTW3 extended status entities (`pet_detected`, `drink_count`, `suspended`, `state_tail_hex`): Supported on `CTW3` only.
- Time schedule entities (`led_on_time`, `led_off_time`, `dnd_start_time`, `dnd_end_time`): Supported on non-CTW3 models.

### 3. Filter Entities during `async_setup_entry`
In `async_setup_entry` for `sensor.py`, `binary_sensor.py`, `number.py`, and `time.py`:
Filter `DESCRIPTIONS` using `description.supported_fn(data)` (resolving `data` from `coordinator.data` or a fallback `PetkitFountainData(alias=model)`) so unsupported entities are never created or registered in Home Assistant.

### 4. Unit Tests
Add unit tests verifying that:
- W4X setup only creates supported entities (no battery, no UVC, no CTW3-only sensors).
- W4XUVC setup creates UVC entity, but no battery/CTW3 entities.
- CTW3 setup creates battery, pet detection, drink count, etc., but no unsupported time entities.
