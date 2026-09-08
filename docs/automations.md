# Home Assistant Automation Examples

Here are practical YAML automation examples for your Petkit smart fountain.

---

## 1. Low Water Level Mobile Notification

Sends a notification to your smartphone when the fountain detects a low water reservoir level.

```yaml
alias: "Petkit: Low Water Level Alert"
description: "Notify when Petkit fountain runs low on water"
trigger:
  - platform: state
    entity_id: binary_sensor.fountain_water_missing
    to: "on"
action:
  - action: notify.notify
    data:
      title: "🚰 Water Fountain Alert"
      message: "Your Petkit fountain water level is low. Please refill the reservoir!"
mode: single
```

---

## 2. Filter Replacement Reminder

Triggers a notification when remaining filter life drops below 10%.

```yaml
alias: "Petkit: Replace Filter Reminder"
description: "Notify when filter life drops below 10%"
trigger:
  - platform: numeric_state
    entity_id: sensor.fountain_filter_life
    below: 10
action:
  - action: notify.notify
    data:
      title: "🧹 Petkit Filter Alert"
      message: "Filter life is at {{ states('sensor.fountain_filter_life') }}%. Remember to order a replacement filter!"
mode: single
```

---

## 3. Low Battery Notification (CTW3 / Eversweet Max 2)

Warns when the internal battery of a cordless CTW3 fountain is running low.

```yaml
alias: "Petkit: Low Battery Alert"
description: "Notify when CTW3 fountain battery is low"
trigger:
  - platform: state
    entity_id: binary_sensor.fountain_low_battery
    to: "on"
action:
  - action: notify.notify
    data:
      title: "🔋 Petkit Battery Low"
      message: "The Petkit fountain battery is low ({{ states('sensor.fountain_battery') }}%). Please connect AC charger."
mode: single
```

---

## 4. Automatic DND (Do Not Disturb) Night Mode

Automatically switches operating mode to Smart and enables DND during sleeping hours.

```yaml
alias: "Petkit: Night Mode"
description: "Set Smart mode and quiet pump at night"
trigger:
  - platform: time
    at: "23:00:00"
action:
  - action: select.select_option
    target:
      entity_id: select.fountain_operating_mode
    data:
      option: "Smart"
mode: single
```
