"""Select platform for Petkit BLE (operation mode)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SET_POWER_MODE
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity
from .protocol import build_change_mode_payload, build_ctw3_select_mode_payload

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
            # CTW3: payload [power, suspend, mode] is built by a dedicated
            # helper that always forces power=1, because selecting a mode in
            # HA implies the user wants that mode to run. See
            # build_ctw3_select_mode_payload for the rationale.
            payload = build_ctw3_select_mode_payload(mode_int)
        else:
            # Generic W5/CTW2: byte[0] = mode (1=normal, 2=smart); selecting a mode implies power-on
            payload = build_change_mode_payload(mode_int)

        _LOGGER.debug(
            "Mode select -> %s (alias=%s): sending CMD 220 payload=%s",
            option,
            data.alias if data is not None else "unknown",
            payload,
        )
        success = await self.coordinator.async_send_command(CMD_SET_POWER_MODE, payload)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set mode to %s", option)
