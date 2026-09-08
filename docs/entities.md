# Entity Reference & Calculation Formulas

This document details every entity provided by the **ha-petkit** integration, including unit types, device applicability, and mathematical formulas used for derived values.

---

## Sensors

| Entity Key | Name | Unit | Device Support | Description |
|---|---|---|---|---|
| `filter_pct` | Filter Life | `%` | All Models | Remaining filter life percentage calculated from pump runtime. |
| `pump_runtime_today` | Pump Runtime Today | `min` | All Models | Accumulated minutes the pump has been active today. |
| `water_purified_today` | Water Purified Today | `L` | All Models | Estimated volume of water filtered today (calculated). |
| `energy_today` | Energy Today | `kWh` | All Models | Estimated electrical energy consumed today (calculated). |
| `filter_days_remaining` | Filter Days Remaining | `d` | All Models | Estimated days before filter replacement is required. |
| `battery` | Battery Level | `%` | CTW3 Only | Current battery state of charge. |
| `rssi` | RSSI | `dBm` | All Models | Signal strength of the Bluetooth connection. |

### Derived Calculation Formulas

#### 1. Water Purified Today (Liters)
$$\text{Liters} = \frac{\text{Flow Rate (LPM)} \times \frac{\text{Pump Runtime Today (min)}}{60}}{\text{Model Divisor}}$$

Where:
- **Flow Rate**: 1.5 LPM
- **Model Divisor**:
  - `CTW3`: 3.0
  - `W5C`: 1.0
  - `W4X`: 1.8
  - `W4XUVC` / `W5` / `W5N` / `CTW2`: 2.0

#### 2. Energy Consumed Today (kWh)
$$\text{Energy (kWh)} = \frac{\text{Power (Watts)} \times \frac{\text{Pump Runtime Today (min)}}{60}}{1000}$$

Where:
- **Power (Watts)**:
  - `W5C`: 0.182 W
  - All other models: 0.75 W

#### 3. Filter Days Remaining (Days)
- **Normal Mode (Continuous)**:
  $$\text{Days} = \left\lceil \frac{\text{Filter Life \%}}{100} \times 60 \right\rceil$$
- **Smart Mode (Intermittent)**:
  $$\text{Days} = \left\lceil \left( \frac{\text{Filter Life \%}}{100} \times 30 \right) \times \frac{\text{Work Min} + \text{Sleep Min}}{\text{Work Min}} \right\rceil$$

---

## Binary Sensors

| Entity Key | Name | Device Support | Description |
|---|---|---|---|
| `pump_running` | Pump Running | All Models | `ON` when the water pump motor is actively running. |
| `water_missing` | Water Missing | All Models | `ON` when the water level reservoir is empty/low. |
| `filter_warning` | Filter Warning | All Models | `ON` when filter life has depleted below threshold. |
| `hardware_failure` | Hardware Failure | All Models | `ON` when a pump motor fault or sensor error is detected. |
| `dnd_active` | DND Active | All Models | `ON` when Do Not Disturb mode is currently active. |
| `pet_detected` | Pet Detected | CTW3 Only | `ON` when proximity/motion sensor detects a pet nearby. |
| `ac_power` | AC Power | CTW3 Only | `ON` when external AC adapter/charging power is plugged in. |
| `low_battery` | Low Battery | CTW3 Only | `ON` when internal battery drops below critical level. |
| `uvc_active` | UVC Active | CTW3 Only | `ON` when UV-C sterilization module is actively running. |

---

## Controls (Switch, Button, Select, Number, Time)

### Switch
- **`switch.<device>_power`**: Turn fountain operation ON or OFF.

### Buttons
- **`button.<device>_reset_filter`**: Resets the internal filter life counter back to 100% (CMD 222).
- **`button.<device>_pump_on`**: Manually turn the pump ON.
- **`button.<device>_pump_off`**: Manually turn the pump OFF.

### Select
- **`select.<device>_operating_mode`**: Choose between `Normal` (continuous pumping) and `Smart` (scheduled work/sleep intervals).

### Numbers & Times
- **`number.<device>_smart_work_duration`**: Active pump duration in Smart mode (minutes).
- **`number.<device>_smart_sleep_duration`**: Rest duration in Smart mode (minutes).
- **`number.<device>_led_brightness`**: LED indicator light brightness.
- **`time.<device>_dnd_start_time` / `dnd_end_time`**: Do Not Disturb schedule period.
