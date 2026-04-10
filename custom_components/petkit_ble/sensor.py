"""Sensor platform for Petkit BLE."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import PetkitFountainData
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity

_LOGGER = logging.getLogger(__name__)


def _format_seconds(total_seconds: int) -> str:
    """Format a duration in seconds as a human-readable string (e.g. '5d 14h 23m 12s')."""
    days, remainder = divmod(int(total_seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


@dataclass(frozen=True, kw_only=True)
class PetkitSensorEntityDescription(SensorEntityDescription):
    """Sensor description with value extractor and optional availability check."""

    value_fn: Callable[[PetkitFountainData], float | int | str | None]
    available_fn: Callable[[PetkitFountainData], bool] = lambda _: True


SENSOR_DESCRIPTIONS: tuple[PetkitSensorEntityDescription, ...] = (
    PetkitSensorEntityDescription(
        key="filter_percent",
        translation_key="filter_percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.filter_percent,
    ),
    PetkitSensorEntityDescription(
        key="pump_runtime_today",
        translation_key="pump_runtime_today",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _format_seconds(d.pump_runtime_today),
    ),
    PetkitSensorEntityDescription(
        key="pump_runtime",
        translation_key="pump_runtime",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _format_seconds(d.pump_runtime),
    ),
    PetkitSensorEntityDescription(
        key="battery_percent",
        translation_key="battery_percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery_percent,
        available_fn=lambda d: d.is_ctw3,
    ),
    PetkitSensorEntityDescription(
        key="battery_voltage_mv",
        translation_key="battery_voltage_mv",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery_voltage_mv,
        available_fn=lambda d: d.is_ctw3,
    ),
    PetkitSensorEntityDescription(
        key="water_purified_today",
        translation_key="water_purified_today",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.water_purified_today_liters, 3),
    ),
    PetkitSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.energy_today_kwh, 6),
    ),
    PetkitSensorEntityDescription(
        key="filter_days_remaining",
        translation_key="filter_days_remaining",
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.filter_days_remaining,
    ),
    PetkitSensorEntityDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.firmware or None,
    ),
    PetkitSensorEntityDescription(
        key="hardware_version",
        translation_key="hardware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.hardware_version or None,
    ),
    PetkitSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE sensors from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities(PetkitBleSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS)


class PetkitBleSensor(PetkitBleEntity, SensorEntity):
    """A sensor entity for Petkit fountain data."""

    entity_description: PetkitSensorEntityDescription

    def __init__(
        self,
        coordinator: PetkitBleCoordinator,
        description: PetkitSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True only when data is present and the device supports this sensor."""
        if not super().available:
            return False
        return self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
