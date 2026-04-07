"""Button platform for Petkit BLE."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import PetkitBleClient
from .const import CMD_RESET_FILTER, CMD_SET_POWER_MODE, CONF_ADDRESS, CONF_MODEL
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PetkitButtonDescription(ButtonEntityDescription):
    """Button description with press action."""

    press_fn: Callable[[PetkitBleCoordinator], list[tuple[int, list[int]]]]


def _reset_filter_cmds(_coordinator: PetkitBleCoordinator) -> list[tuple[int, list[int]]]:
    return [(CMD_RESET_FILTER, [0])]


def _pump_on_cmds(coordinator: PetkitBleCoordinator) -> list[tuple[int, list[int]]]:
    mode = coordinator.data.mode if coordinator.data else 1
    return [(CMD_SET_POWER_MODE, [1, mode])]


def _pump_off_cmds(coordinator: PetkitBleCoordinator) -> list[tuple[int, list[int]]]:
    mode = coordinator.data.mode if coordinator.data else 1
    return [(CMD_SET_POWER_MODE, [0, mode])]


BUTTON_DESCRIPTIONS: tuple[PetkitButtonDescription, ...] = (
    PetkitButtonDescription(
        key="reset_filter",
        translation_key="reset_filter",
        press_fn=_reset_filter_cmds,
    ),
    PetkitButtonDescription(
        key="pump_on",
        translation_key="pump_on",
        press_fn=_pump_on_cmds,
    ),
    PetkitButtonDescription(
        key="pump_off",
        translation_key="pump_off",
        press_fn=_pump_off_cmds,
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
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the button command to the device."""
        address: str = self.coordinator.config_entry.data[CONF_ADDRESS]
        alias: str = self.coordinator.config_entry.data[CONF_MODEL]

        ble_device = async_ble_device_from_address(self.coordinator.hass, address, connectable=True)
        if ble_device is None:
            _LOGGER.warning("Cannot press %s: device %s not found", self.entity_description.key, address)
            return

        client = PetkitBleClient(ble_device)
        for cmd, data in self.entity_description.press_fn(self.coordinator):
            success = await client.async_send_command(cmd, data, alias)
            if not success:
                _LOGGER.error("Failed to send CMD %d for %s", cmd, self.entity_description.key)
                return

        await self.coordinator.async_request_refresh()
