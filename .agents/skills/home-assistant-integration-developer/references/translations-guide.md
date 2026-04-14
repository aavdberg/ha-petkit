# Translations Guide

## strings.json

`strings.json` defines the base English structure for shared translation content such as
config flows, options flows, errors, and abort reasons. In this repository, entity names
are currently stored in `translations/en.json` and mirrored to the other files in
`translations/`, rather than being defined in `strings.json`.

Example `strings.json` structure:

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
  }
}
```

If you want `strings.json` to be the single source of truth for entity names too, you must
explicitly duplicate the `entity.<platform>.<key>.name` keys there and keep them in sync
with `translations/*.json`.

## Translation Keys

Entity names are resolved via `translation_key`:

```python
MySensorDescription(
    key="filter_percent",
    translation_key="filter_percent",
    ...
)
```

For entity names in this repository, the `translation_key` maps to
`translations/<language>.json` → `entity.<platform>.<key>.name`.

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
2. Add the name to `translations/en.json` under `entity.<platform>.<key>.name`
3. Mirror the key to all other files in `translations/` (nl.json, uk.json, etc.)
4. Translate the name for each language file
5. If you want `strings.json` to remain the single source of truth, also duplicate the
   same entity key there and keep both locations in sync

## Translation Files

Files in `translations/` contain the runtime language data used by Home Assistant:

```
translations/
├── en.json    # English
├── nl.json    # Dutch
├── uk.json    # Ukrainian
└── ...
```

In this repository, config-flow strings should stay aligned with `strings.json`, while
entity translations may live directly in `translations/*.json`.

Keep all translation files in sync. When adding entity keys to `translations/en.json`,
add corresponding keys to all other translation files as well.
