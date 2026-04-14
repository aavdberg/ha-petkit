# Entity Guide

## Base Entity

All entities inherit from a base `CoordinatorEntity` subclass:

```python
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

class MyBaseEntity(CoordinatorEntity[MyCoordinator]):
    """Base entity for My Integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.device_name,
            manufacturer="Manufacturer",
            model=coordinator.model,
        )
```

## Entity Descriptions

Use frozen dataclasses with callable extractors:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

@dataclass(frozen=True, kw_only=True)
class MySensorDescription(SensorEntityDescription):
    """Sensor description with value extractor."""

    value_fn: Callable[[MyDataClass], float | str | None]
    available_fn: Callable[[MyDataClass], bool] = lambda _: True
```

**Why frozen?** Descriptions are shared across all instances of an entity type.
Mutable state would cause bugs.

Define descriptions as a tuple:

```python
SENSOR_DESCRIPTIONS: tuple[MySensorDescription, ...] = (
    MySensorDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
)
```

## Platform Setup

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        MySensor(coordinator, desc)
        for desc in SENSOR_DESCRIPTIONS
        if desc.available_fn(coordinator.data)  # Only add relevant entities
    )
```

## Unique ID

Format: `{normalized_address}_{key}`

```python
from homeassistant.helpers import device_registry as dr

self._attr_unique_id = (
    f"{dr.format_mac(coordinator.address)}_{description.key}"
)
```

Use `dr.format_mac()` to normalize MAC addresses.

## Availability

Entity is available when coordinator has data:

```python
@property
def available(self) -> bool:
    """Return True if entity is available."""
    return super().available and self.entity_description.available_fn(
        self.coordinator.data
    )
```

## Properties Must Be O(1)

Entity properties must only extract from `coordinator.data`:

```python
# ✅ Good — O(1) data extraction
@property
def native_value(self):
    return self.entity_description.value_fn(self.coordinator.data)

# ❌ Bad — network I/O in property
@property
def native_value(self):
    return await self.client.fetch_temperature()  # NEVER DO THIS
```

## State Classes

| Class | Use when |
|---|---|
| `MEASUREMENT` | Value is a point-in-time reading (temperature, humidity) |
| `TOTAL` | Monotonically increasing total that can reset (energy meter) |
| `TOTAL_INCREASING` | Monotonically increasing, HA auto-detects resets |

**Caution with `TOTAL_INCREASING`**: Only use when the device persists the counter.
If the counter resets on power cycle / reconnect, use `MEASUREMENT` or persist with
`RestoreEntity`.

## Device Info

One `DeviceInfo` per physical device. All entities for the same device share identifiers:

```python
DeviceInfo(
    identifiers={(DOMAIN, address)},
    connections={(dr.CONNECTION_BLUETOOTH, address)},  # For BLE
    name="My Device",
    manufacturer="Manufacturer",
    model="Model Name",
    sw_version=coordinator.firmware_version,
)
```

## Platform Reference

| Platform | Entity base | Description base | Use case |
|---|---|---|---|
| `sensor` | `SensorEntity` | `SensorEntityDescription` | Read-only values |
| `binary_sensor` | `BinarySensorEntity` | `BinarySensorEntityDescription` | On/off states |
| `switch` | `SwitchEntity` | `SwitchEntityDescription` | On/off controls |
| `button` | `ButtonEntity` | `ButtonEntityDescription` | Fire-and-forget actions |
| `number` | `NumberEntity` | `NumberEntityDescription` | Numeric settings (min/max/step) |
| `select` | `SelectEntity` | `SelectEntityDescription` | Dropdown choices |
| `time` | `TimeEntity` | `TimeEntityDescription` | Time-of-day settings |
