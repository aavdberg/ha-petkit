---
name: home-assistant-integration-developer
description: >
  Best practices for developing Home Assistant custom integrations — config flows, coordinators,
  entity platforms, BLE protocol, translations, manifest, and code quality.

  TRIGGER THIS SKILL WHEN:
  - Creating or modifying a Home Assistant custom integration
  - Adding new entity platforms (sensor, switch, number, time, select, button, binary_sensor)
  - Writing or refactoring a config flow (user, bluetooth, options)
  - Implementing a DataUpdateCoordinator for polling or push data
  - Creating BLE/Bluetooth integrations with bleak or HA bluetooth stack
  - Adding translation strings or entity descriptions
  - Setting up manifest.json with BLE matchers or dependencies
  - Writing entity description dataclasses with value extractors
  - Implementing device commands (write-back) through coordinator
  - Structuring __init__.py setup/unload with runtime_data pattern

  SYMPTOMS:
  - Agent creates entities in __init__.py instead of platform files
  - Agent uses hass.data[DOMAIN] instead of entry.runtime_data pattern
  - Agent does network I/O in entity properties instead of coordinator
  - Agent skips DataUpdateCoordinator and polls directly from entities
  - Agent uses device_id instead of entity_id in entity unique IDs
  - Agent forgets from __future__ import annotations or type hints
  - Agent imports Callable from typing instead of collections.abc
  - Agent duplicates payload-building logic across multiple platform files
  - Agent uses mutable state in entity description dataclasses (missing frozen=True)
  - Agent stores secrets in code instead of config entry data
  - Agent skips translation_key and hardcodes entity names
  - Agent catches bare Exception without re-raising as UpdateFailed
  - Agent creates config entries without calling async_set_unique_id first
  - Agent accesses private fields (_underscore) across module boundaries

metadata:
  version: 1
---

# Home Assistant Integration Developer

**Core principle:** Follow Home Assistant's native patterns — `DataUpdateCoordinator` for data fetching, `entry.runtime_data` for state, `CoordinatorEntity` for entities, frozen dataclass descriptions for entity metadata, and `strings.json` for all user-visible text.

## Decision Workflow

Follow this sequence when creating or modifying an integration:

### 0. Gate: Custom integration or core?

This skill covers **custom integrations** installed via HACS or manually in `custom_components/`.
Core integrations follow stricter rules (quality scale, hassfest). The patterns here are compatible
with both but optimized for custom component development.

### 1. Project structure

Every integration lives in `custom_components/<domain>/` with this layout:

```
custom_components/<domain>/
├── __init__.py          # Setup/unload, platform forwarding
├── manifest.json        # Metadata, dependencies, BLE matchers
├── const.py             # All constants (UUIDs, command IDs, defaults)
├── config_flow.py       # Config flow + options flow
├── coordinator.py       # DataUpdateCoordinator
├── entity.py            # Base entity class (CoordinatorEntity)
├── protocol.py          # Protocol helpers (payload builders, shared logic)
├── <client>.py          # Device client (BLE, API, etc.)
├── sensor.py            # Sensor platform
├── binary_sensor.py     # Binary sensor platform
├── switch.py            # Switch platform
├── button.py            # Button platform
├── number.py            # Number platform
├── time.py              # Time platform
├── select.py            # Select platform
├── strings.json         # Source-of-truth translations (English)
└── translations/        # Per-language translations
    ├── en.json
    └── <lang>.json
```

### 2. Manifest.json

Required fields:
```json
{
  "domain": "my_integration",
  "name": "My Integration",
  "version": "1.0.0",
  "config_flow": true,
  "documentation": "https://github.com/...",
  "issue_tracker": "https://github.com/.../issues",
  "requirements": [],
  "dependencies": [],
  "codeowners": ["@username"],
  "iot_class": "local_polling"
}
```

For Bluetooth integrations, add:
```json
{
  "bluetooth": [{"connectable": true, "local_name": "DeviceName_*"}],
  "dependencies": ["bluetooth", "bluetooth_adapters"]
}
```

See `references/manifest-guide.md` for all fields and iot_class values.

### 3. Config flow pattern

See `references/config-flow-guide.md` for detailed patterns. Key rules:

- Always call `async_set_unique_id()` + `self._abort_if_unique_id_configured()` first
- Normalize MAC addresses to uppercase
- Store secrets in `config_entry.data[CONF_SECRET]`, never in code
- Use `vol.Schema` for input validation
- Keep config flow lightweight — no heavy I/O
- For Bluetooth: implement `async_step_bluetooth()` for auto-discovery

### 4. DataUpdateCoordinator

See `references/coordinator-guide.md`. Key rules:

- One coordinator per config entry, stored in `entry.runtime_data`
- Override `_async_update_data()` — raise `UpdateFailed` on errors
- Use `asyncio.Lock()` for serial device access (BLE, serial ports)
- Call `async_request_refresh()` after write commands
- Never do I/O outside the coordinator

### 5. Entity pattern

See `references/entity-guide.md`. Key rules:

- All entities inherit from a base `CoordinatorEntity` subclass
- Use frozen dataclass descriptions with `value_fn` / `available_fn`
- Set `_attr_has_entity_name = True` for automatic naming
- Unique ID format: `{normalized_address}_{key}`
- Properties must be O(1) — extract from `coordinator.data` only
- Return `None` when data is unavailable

### 6. Code quality

- `from __future__ import annotations` in every file
- Full type annotations on all functions and parameters
- `Callable` from `collections.abc`, not `typing`
- Use `| None` instead of `Optional[]`
- Ruff for linting and formatting
- Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)

---

## Critical Anti-Patterns

| Anti-pattern | Use instead | Why | Reference |
|---|---|---|---|
| `hass.data[DOMAIN][entry_id]` | `entry.runtime_data` | Modern pattern (HA 2024.1+), type-safe, auto-cleanup | `references/coordinator-guide.md` |
| Network I/O in entity property | `coordinator._async_update_data()` | Properties must be sync and O(1) | `references/entity-guide.md` |
| Creating entities in `__init__.py` | `async_setup_entry()` in platform files | Platform forwarding ensures proper lifecycle | `references/entity-guide.md` |
| `from typing import Callable` | `from collections.abc import Callable` | Python 3.12+ / ruff UP035 | `references/code-quality.md` |
| Bare `except Exception` in coordinator | `except SpecificError as err: raise UpdateFailed(...) from err` | Preserve error chain, don't swallow bugs | `references/coordinator-guide.md` |
| Mutable entity description | `@dataclass(frozen=True, kw_only=True)` | Descriptions are shared across instances | `references/entity-guide.md` |
| Duplicated logic across platforms | Shared helper in `protocol.py` | Single source of truth for payload building | `references/entity-guide.md` |
| Private field access across modules | Make fields public or use properties | `data._field` breaks encapsulation | `references/code-quality.md` |
| Hardcoded entity names | `translation_key` + `strings.json` | Required for multi-language support | `references/translations-guide.md` |
| `TOTAL_INCREASING` for in-memory counter | `MEASUREMENT` or persist with `RestoreEntity` | Resets on restart look like counter decreases | `references/entity-guide.md` |
| `struct.pack(">q", id)` for unsigned IDs | `struct.pack(">Q", id)` (unsigned) | High-bit IDs raise `struct.error` with signed | `references/code-quality.md` |
| Config entry without `async_set_unique_id` | Always set unique ID first | Prevents duplicate entries | `references/config-flow-guide.md` |
| Secrets in source code | `config_entry.data[CONF_SECRET]` | Secrets must be stored encrypted in config | `references/config-flow-guide.md` |
| `bytes.fromhex()` without try/except | Wrap in try/except ValueError | Corrupted config data crashes integration | `references/coordinator-guide.md` |

---

## Reference Files

Read these when you need detailed information:

| File | When to read | Key sections |
|------|--------------|--------------|
| `references/manifest-guide.md` | Creating or updating manifest.json | `#required-fields`, `#bluetooth-matchers`, `#iot-class`, `#dependencies` |
| `references/config-flow-guide.md` | Writing config flows (user, bluetooth, options) | `#bluetooth-discovery`, `#user-step`, `#options-flow`, `#unique-id`, `#secrets` |
| `references/coordinator-guide.md` | Implementing DataUpdateCoordinator | `#setup-pattern`, `#error-handling`, `#write-commands`, `#locking`, `#runtime-data` |
| `references/entity-guide.md` | Creating entity platforms and descriptions | `#base-entity`, `#descriptions`, `#device-info`, `#availability`, `#platforms` |
| `references/translations-guide.md` | Adding or updating translation strings | `#strings-json`, `#translation-keys`, `#config-flow-strings`, `#entity-names` |
| `references/ble-integration-guide.md` | Building Bluetooth/BLE integrations | `#gatt-characteristics`, `#frame-format`, `#authentication`, `#esphome-proxies` |
| `references/code-quality.md` | Code style, type hints, linting, testing | `#type-hints`, `#ruff`, `#imports`, `#testing` |
