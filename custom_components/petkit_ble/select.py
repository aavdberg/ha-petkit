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
        """Send CMD 220 to change mode.

        Per the reverse-engineered W5 protocol, CMD 220 byte[0] encodes both power
        and mode as a single value: 0=off, 1=normal (on), 2=smart (on).
        CTW3 uses a 3-byte layout [power, suspend, mode] matching its CMD 210 response.
        """
        mode_int = _MODE_TO_INT[option]
        data = self.coordinator.data

        if data is not None and data.is_ctw3:
            # CTW3: [power, suspend_status=0, mode]
            power = data.power_status if data.power_status in (0, 1) else 1
            payload = [power, 0, mode_int]
        else:
            # Generic W5/CTW2: byte[0] = mode (1=normal, 2=smart); selecting a mode implies power-on
            payload = [mode_int, 0]

        success = await self.coordinator.async_send_command(CMD_SET_POWER_MODE, payload)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set mode to %s", option)
