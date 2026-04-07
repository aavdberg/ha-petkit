"""Select platform for Petkit BLE (operation mode)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SET_POWER_MODE
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity

_LOGGER = logging.getLogger(__name__)

# Map HA option strings → Petkit mode integers
_MODE_TO_INT: dict[str, int] = {"normal": 1, "smart": 2}
_INT_TO_MODE: dict[int, str] = {v: k for k, v in _MODE_TO_INT.items()}

MODE_SELECT_DESCRIPTION = SelectEntityDescription(
    key="mode",
    translation_key="mode",
    options=["normal", "smart"],
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE select entities from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities([PetkitModeSelect(coordinator)])


class PetkitModeSelect(PetkitBleEntity, SelectEntity):
    """Select entity to choose between Normal and Smart pump mode."""

    def __init__(self, coordinator: PetkitBleCoordinator) -> None:
        """Initialise the mode select."""
        super().__init__(coordinator, MODE_SELECT_DESCRIPTION.key)
        self.entity_description = MODE_SELECT_DESCRIPTION

    @property
    def current_option(self) -> str | None:
        """Return the current mode as an option string."""
        if self.coordinator.data is None:
            return None
        return _INT_TO_MODE.get(self.coordinator.data.mode, "normal")

    async def async_select_option(self, option: str) -> None:
        """Send CMD 220 to change mode while preserving the current power state."""
        mode_int = _MODE_TO_INT[option]
        # Keep the current power state; default to 1 (on) if unknown.
        raw_power = self.coordinator.data.power_status if self.coordinator.data else 1
        power = raw_power if raw_power in (0, 1) else 1

        success = await self.coordinator.async_send_command(CMD_SET_POWER_MODE, [power, mode_int])
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set mode to %s", option)
