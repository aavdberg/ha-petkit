"""Binary sensor platform for Petkit BLE."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import PetkitFountainData
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PetkitBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with value and availability callables."""

    value_fn: Callable[[PetkitFountainData], bool]
    available_fn: Callable[[PetkitFountainData], bool] = lambda _: True


BINARY_SENSOR_DESCRIPTIONS: tuple[PetkitBinarySensorDescription, ...] = (
    PetkitBinarySensorDescription(
        key="pump_running",
        translation_key="pump_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.is_pump_running,
    ),
    PetkitBinarySensorDescription(
        key="warning_water_missing",
        translation_key="warning_water_missing",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: bool(d.warning_water_missing),
    ),
    PetkitBinarySensorDescription(
        key="warning_filter",
        translation_key="warning_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: bool(d.warning_filter),
    ),
    PetkitBinarySensorDescription(
        key="warning_breakdown",
        translation_key="warning_breakdown",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: bool(d.warning_breakdown),
    ),
    PetkitBinarySensorDescription(
        key="dnd_active",
        translation_key="dnd_active",
        value_fn=lambda d: bool(d.dnd_state),
    ),
    PetkitBinarySensorDescription(
        key="pet_detected",
        translation_key="pet_detected",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        value_fn=lambda d: bool(d.detect_status),
        available_fn=lambda d: d.is_ctw3,
    ),
    PetkitBinarySensorDescription(
        key="on_ac_power",
        translation_key="on_ac_power",
        device_class=BinarySensorDeviceClass.PLUG,
        # electric_status == 2 means AC power
        value_fn=lambda d: d.electric_status == 2,
        available_fn=lambda d: d.is_ctw3,
    ),
    PetkitBinarySensorDescription(
        key="low_battery",
        translation_key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda d: bool(d.low_battery),
        available_fn=lambda d: d.is_ctw3,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE binary sensors from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities(
        PetkitBleBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class PetkitBleBinarySensor(PetkitBleEntity, BinarySensorEntity):
    """A binary sensor entity for Petkit fountain data."""

    entity_description: PetkitBinarySensorDescription

    def __init__(
        self,
        coordinator: PetkitBleCoordinator,
        description: PetkitBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True only when data is present and the device supports this sensor."""
        if not super().available:
            return False
        return self.entity_description.available_fn(self.coordinator.data)

    @property
    def is_on(self) -> bool | None:
        """Return True when the condition is active."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
