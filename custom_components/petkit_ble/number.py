"""Number platform for Petkit BLE (smart mode timers, LED brightness, battery intervals)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import PetkitFountainData
from .const import CMD_WRITE_SETTINGS
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity
from .protocol import build_full_settings_payload

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PetkitNumberDescription(NumberEntityDescription):
    """Number description with value extractor and setter field name."""

    value_fn: Callable[[PetkitFountainData], float | None]
    available_fn: Callable[[PetkitFountainData], bool] = lambda _: True
    field_name: str


NUMBER_DESCRIPTIONS: tuple[PetkitNumberDescription, ...] = (
    PetkitNumberDescription(
        key="smart_work_minutes",
        translation_key="smart_work_minutes",
        native_min_value=1,
        native_max_value=60,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda d: d.smart_time_on,
        field_name="smart_time_on",
    ),
    PetkitNumberDescription(
        key="smart_sleep_minutes",
        translation_key="smart_sleep_minutes",
        native_min_value=1,
        native_max_value=60,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda d: d.smart_time_off,
        field_name="smart_time_off",
    ),
    PetkitNumberDescription(
        key="led_brightness",
        translation_key="led_brightness",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: d.led_brightness,
        field_name="led_brightness",
    ),
    PetkitNumberDescription(
        key="battery_work_seconds",
        translation_key="battery_work_seconds",
        native_min_value=1,
        native_max_value=3600,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda d: d.battery_work_time,
        available_fn=lambda d: d.is_ctw3,
        field_name="battery_work_time",
    ),
    PetkitNumberDescription(
        key="battery_sleep_seconds",
        translation_key="battery_sleep_seconds",
        native_min_value=1,
        native_max_value=7200,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda d: d.battery_sleep_time,
        available_fn=lambda d: d.is_ctw3,
        field_name="battery_sleep_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE number entities from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities(PetkitBleNumber(coordinator, desc) for desc in NUMBER_DESCRIPTIONS)


class PetkitBleNumber(PetkitBleEntity, NumberEntity):
    """A number entity for Petkit fountain settings."""

    entity_description: PetkitNumberDescription

    def __init__(
        self,
        coordinator: PetkitBleCoordinator,
        description: PetkitNumberDescription,
    ) -> None:
        """Initialise the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True only when data is present and the device supports this entity."""
        if not super().available:
            return False
        return self.entity_description.available_fn(self.coordinator.data)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value by writing full settings via CMD 221."""
        data = self.coordinator.data
        if data is None:
            return
        payload = build_full_settings_payload(data, **{self.entity_description.field_name: int(value)})
        success = await self.coordinator.async_send_command(CMD_WRITE_SETTINGS, payload)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %s", self.entity_description.key, value)
