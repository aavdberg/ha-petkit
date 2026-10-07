"""Button platform for Petkit BLE."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ENTITY_ID_FORMAT, ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_RESET_FILTER
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PetkitButtonDescription(ButtonEntityDescription):
    """Button description with press action."""

    press_fn: Callable[[PetkitBleCoordinator], list[tuple[int, list[int]]]] | None = None
    async_press_fn: Callable[[PetkitBleCoordinator], Coroutine[Any, Any, None]] | None = None


def _reset_filter_cmds(_coordinator: PetkitBleCoordinator) -> list[tuple[int, list[int]]]:
    return [(CMD_RESET_FILTER, [])]


BUTTON_DESCRIPTIONS: tuple[PetkitButtonDescription, ...] = (
    PetkitButtonDescription(
        key="reset_filter",
        translation_key="reset_filter",
        press_fn=_reset_filter_cmds,
    ),
    PetkitButtonDescription(
        key="reset_clean",
        translation_key="reset_clean",
        async_press_fn=lambda coordinator: coordinator.async_reset_last_cleaned(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE buttons from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities(PetkitBleButton(coordinator, description) for description in BUTTON_DESCRIPTIONS)


class PetkitBleButton(PetkitBleEntity, ButtonEntity):
    """A button entity for Petkit fountain control actions."""

    entity_description: PetkitButtonDescription

    def __init__(
        self,
        coordinator: PetkitBleCoordinator,
        description: PetkitButtonDescription,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator, description.key, ENTITY_ID_FORMAT)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the button command or execute action."""
        if self.entity_description.async_press_fn is not None:
            await self.entity_description.async_press_fn(self.coordinator)
            return

        if self.entity_description.press_fn is not None:
            for cmd, data in self.entity_description.press_fn(self.coordinator):
                success = await self.coordinator.async_send_command(cmd, data)
                if not success:
                    _LOGGER.error("Failed to send CMD %d for %s", cmd, self.entity_description.key)
                    return

            await self.coordinator.async_request_refresh()
