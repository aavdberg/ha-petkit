"""Time platform for Petkit BLE (LED and DND schedules)."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import PetkitFountainData
from .const import CMD_WRITE_SETTINGS, CTW3_ALIASES
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity
from .protocol import build_full_settings_payload

_LOGGER = logging.getLogger(__name__)


def _minutes_to_time(minutes: int) -> datetime.time:
    """Convert minutes-from-midnight to a time object."""
    safe = minutes % 1440
    return datetime.time(safe // 60, safe % 60)


def _time_to_minutes(t: datetime.time) -> int:
    """Convert a time object to minutes-from-midnight."""
    return t.hour * 60 + t.minute


@dataclass(frozen=True, kw_only=True)
class PetkitTimeDescription(TimeEntityDescription):
    """Time description with value extractor and setter field name."""

    value_fn: Callable[[PetkitFountainData], int]
    field_name: str
    available_fn: Callable[[PetkitFountainData], bool] = lambda _: True


TIME_DESCRIPTIONS: tuple[PetkitTimeDescription, ...] = (
    PetkitTimeDescription(
        key="led_on_time",
        translation_key="led_on_time",
        value_fn=lambda d: d.led_on_minutes,
        field_name="led_on_minutes",
        available_fn=lambda d: d.alias not in CTW3_ALIASES,
    ),
    PetkitTimeDescription(
        key="led_off_time",
        translation_key="led_off_time",
        value_fn=lambda d: d.led_off_minutes,
        field_name="led_off_minutes",
        available_fn=lambda d: d.alias not in CTW3_ALIASES,
    ),
    PetkitTimeDescription(
        key="dnd_start_time",
        translation_key="dnd_start_time",
        value_fn=lambda d: d.dnd_start_minutes,
        field_name="dnd_start_minutes",
        available_fn=lambda d: d.alias not in CTW3_ALIASES,
    ),
    PetkitTimeDescription(
        key="dnd_end_time",
        translation_key="dnd_end_time",
        value_fn=lambda d: d.dnd_end_minutes,
        field_name="dnd_end_minutes",
        available_fn=lambda d: d.alias not in CTW3_ALIASES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE time entities from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities(PetkitBleTime(coordinator, desc) for desc in TIME_DESCRIPTIONS)


class PetkitBleTime(PetkitBleEntity, TimeEntity):
    """A time entity for Petkit fountain schedule settings."""

    entity_description: PetkitTimeDescription

    def __init__(
        self,
        coordinator: PetkitBleCoordinator,
        description: PetkitTimeDescription,
    ) -> None:
        """Initialise the time entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True only when data is present and the device supports this entity."""
        if not super().available:
            return False
        return self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> datetime.time | None:
        """Return the current time value."""
        if self.coordinator.data is None:
            return None
        minutes = self.entity_description.value_fn(self.coordinator.data)
        return _minutes_to_time(minutes)

    async def async_set_value(self, value: datetime.time) -> None:
        """Set a new time by writing full settings via CMD 221."""
        data = self.coordinator.data
        if data is None:
            return
        minutes = _time_to_minutes(value)
        payload = build_full_settings_payload(data, **{self.entity_description.field_name: minutes})
        success = await self.coordinator.async_send_command(CMD_WRITE_SETTINGS, payload)
        if success:
            self.coordinator.apply_setting_optimistic(self.entity_description.field_name, minutes)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s", self.entity_description.key)
