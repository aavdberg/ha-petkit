# Translations Guide

## strings.json

`strings.json` is the **source of truth** for all user-visible text. It uses English as
the base language and follows this structure:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Configure Device",
        "description": "Enter the BLE address of your device.",
        "data": {
          "address": "Bluetooth address",
          "name": "Device name"
        }
      },
      "bluetooth_confirm": {
        "description": "Confirm setup of {name}"
      }
    },
    "abort": {
      "already_configured": "Device already configured",
      "cannot_connect": "Unable to connect to device"
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "unknown": "Unexpected error"
    }
  },
  "entity": {
    "sensor": {
      "filter_percent": {
        "name": "Filter life"
      },
      "pump_runtime_today": {
        "name": "Pump runtime today"
      }
    },
    "switch": {
      "power": {
        "name": "Power"
      }
    }
  }
}
```

## Translation Keys

Entity names are resolved via `translation_key`:

```python
MySensorDescription(
    key="filter_percent",
    translation_key="filter_percent",
    ...
)
```

The `translation_key` maps to `strings.json` → `entity.<platform>.<key>.name`.

## Entity Names

With `_attr_has_entity_name = True`, the entity's display name is:
`<Device Name> <Entity Name from translation>`

Example: If device is "Petkit CTW3" and entity translation is "Filter life",
the entity shows as "Petkit CTW3 Filter life".

## Config Flow Strings

Config flow steps, errors, and abort reasons are under the `config` key.
Options flow strings go under `options`.

## Adding New Entities

When adding a new entity:

1. Add the description to the platform file with `translation_key`
2. Add the name to `strings.json` under `entity.<platform>.<key>.name`
3. Mirror to all files in `translations/` (en.json, nl.json, uk.json, etc.)
4. Translate the name for each language file

## Translation Files

Files in `translations/` mirror the structure of `strings.json`:

```
translations/
├── en.json    # English (should match strings.json)
├── nl.json    # Dutch
├── uk.json    # Ukrainian
└── ...
```

Keep all translation files in sync. When adding keys to `strings.json`,
add corresponding keys to all translation files.
