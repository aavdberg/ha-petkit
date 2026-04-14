# Manifest Guide

## Required Fields

Every `manifest.json` must include:

| Field | Type | Description |
|---|---|---|
| `domain` | string | Unique identifier, snake_case, matches folder name |
| `name` | string | Human-readable name |
| `version` | string | Semantic version (e.g., `1.2.3`) |
| `config_flow` | boolean | `true` if integration has a config flow |
| `documentation` | string | URL to documentation |
| `requirements` | list | PyPI packages needed (e.g., `["bleak>=0.21.1"]`) |
| `dependencies` | list | Other HA integrations required |
| `codeowners` | list | GitHub usernames (e.g., `["@username"]`) |
| `iot_class` | string | How the integration communicates |

## IoT Class

| Value | Description |
|---|---|
| `local_polling` | Local device, integration polls for data |
| `local_push` | Local device, device pushes data |
| `cloud_polling` | Cloud API, integration polls |
| `cloud_push` | Cloud API, cloud pushes data |
| `assumed_state` | No feedback from device, state is assumed |

## Bluetooth Matchers

For BLE integrations, add `bluetooth` key with matchers:

```json
{
  "bluetooth": [
    {
      "connectable": true,
      "local_name": "CTW3*"
    }
  ],
  "dependencies": ["bluetooth", "bluetooth_adapters"]
}
```

Matcher fields:
- `local_name`: BLE advertised name (supports `*` wildcard at end)
- `service_uuid`: GATT service UUID
- `manufacturer_id`: Bluetooth manufacturer ID
- `manufacturer_data_start`: First bytes of manufacturer data (hex)
- `connectable`: Whether device must be connectable

Multiple matchers can be provided as an array — any match triggers discovery.

## Dependencies

Common dependencies for BLE integrations:
```json
"dependencies": ["bluetooth", "bluetooth_adapters"]
```

This enables HA's Bluetooth stack including ESPHome proxy support.
