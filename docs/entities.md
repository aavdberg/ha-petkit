# Entity Reference & Calculation Formulas

This document details every entity provided by the **ha-petkit** integration, including unit types, device applicability, and mathematical formulas used for derived values.

---

## Sensors

| Entity Key | Name | Unit | Device Support | Description |
|---|---|---|---|---|
| `filter_percent` | Filter Life | `%` | All Models | Remaining filter life percentage calculated from pump runtime. |
| `pump_runtime_today` | Pump Runtime Today | `s` | All Models | Accumulated seconds the pump has been active today. |
| `pump_runtime` | Total Pump Runtime | `s` | All Models | Total lifetime seconds the pump has been active. |
| `water_purified_today` | Water Purified Today | `L` | All Models | Estimated volume of water filtered today (calculated). |
| `power` | Power | `W` | All Models | Estimated current power consumption in Watts. |
| `energy_today` | Energy Today | `kWh` | All Models | Estimated electrical energy consumed today (calculated). |
| `energy_today_wh` | Energy Today (Wh) | `Wh` | All Models | Estimated electrical energy consumed today in Watt-hours. |
| `filter_days_remaining` | Filter Days Remaining | `d` | All Models | Estimated days before filter replacement is required. |
| `battery_percent` | Battery Level | `%` | CTW3 Only | Current battery state of charge. |
| `battery_voltage_mv` | Battery Voltage | `mV` | CTW3 Only | Current battery terminal voltage in millivolts. |
| `drink_count` | Drink Count | — | CTW3 Only | Number of drinking sessions recorded today. |
| `firmware` | Firmware Version | — | All Models | Device firmware version string. |
| `hardware_version` | Hardware Version | — | All Models | Device hardware revision string. |
| `rssi` | RSSI | `dBm` | All Models | Signal strength of the Bluetooth connection. |

### Derived Calculation Formulas

#### 1. Water Purified Today (Liters)
$$\text{Liters} = \frac{\text{Flow Rate (1.5 LPM)} \times \frac{\text{Pump Runtime Today (s)}}{3600}}{\text{Model Divisor}}$$

Where:
- **Flow Rate**: 1.5 LPM
- **Model Divisor**:
  - `CTW3`: 3.0
  - `W5C`: 1.0
  - `W4X`: 1.8
  - `W4XUVC` / `W5` / `W5N` / `CTW2`: 2.0

#### 2. Energy Consumed Today (kWh)
$$\text{Energy (kWh)} = \frac{\text{Power (Watts)} \times \frac{\text{Pump Runtime Today (s)}}{3600}}{1000}$$

Where:
- **Power (Watts)**:
  - `W5C`: 0.182 W
  - All other models: 0.75 W

#### 3. Filter Days Remaining (Days)
- **Normal Mode (Continuous)**:
  $$\text{Days} = \left\lceil \frac{\text{Filter Percent}}{100} \times 60 \right\rceil$$
- **Smart Mode (Intermittent)**:
  $$\text{Days} = \left\lceil \left( \frac{\text{Filter Percent}}{100} \times 30 \right) \times \frac{\text{Work Min} + \text{Sleep Min}}{\text{Work Min}} \right\rceil$$

---

## Binary Sensors

| Entity Key | Name | Device Support | Description |
|---|---|---|---|
| `pump_running` | Pump Running | All Models | `ON` when the water pump motor is actively running. |
| `warning_water_missing` | Water Missing | All Models | `ON` when the water level reservoir is empty/low. |
| `warning_filter` | Filter Warning | All Models | `ON` when filter life has depleted below threshold. |
| `warning_breakdown` | Hardware Failure | All Models | `ON` when a pump motor fault or sensor error is detected. |
| `dnd_active` | DND Active | All Models | `ON` when Do Not Disturb mode is currently active. |
| `pet_detected` | Pet Detected | CTW3 Only | `ON` when proximity/motion sensor detects a pet nearby. |
| `on_ac_power` | AC Power | CTW3 Only | `ON` when external AC adapter/charging power is plugged in. |
| `low_battery` | Low Battery | CTW3 Only | `ON` when internal battery drops below critical level. |
| `suspended` | Suspended | CTW3 Only | `ON` when device pumping schedule is suspended. |
| `uvc_active` | UVC Active | CTW3 Only | `ON` when UV-C sterilization module is actively running. |

---

## Controls (Switch, Button, Select, Number, Time)

### Switches
- **`switch.<device>_power`**: Turn fountain pump power ON or OFF.
- **`switch.<device>_led`**: Toggle LED indicator light ON or OFF (CMD 221).
- **`switch.<device>_do_not_disturb`**: Toggle Do Not Disturb mode ON or OFF (CMD 221).
- **`switch.<device>_child_lock`**: Toggle button child lock ON or OFF (CMD 221).

### Button
- **`button.<device>_reset_filter`**: Resets the internal filter life counter back to 100% (CMD 222).

### Select
- **`select.<device>_mode`**: Choose between operating modes `normal` (continuous pumping) and `smart` (scheduled work/sleep intervals).

### Numbers & Times
- **`number.<device>_smart_work_minutes`**: Active pump duration in Smart mode (minutes).
- **`number.<device>_smart_sleep_minutes`**: Rest duration in Smart mode (minutes).
- **`number.<device>_led_brightness`**: LED indicator light brightness (0-3 for CTW3, 0-10 for others).
- **`time.<device>_led_on_time` / `led_off_time`**: LED schedule start & end times (Non-CTW3 models only).
- **`time.<device>_dnd_start_time` / `dnd_end_time`**: Do Not Disturb schedule period (Non-CTW3 models only).
