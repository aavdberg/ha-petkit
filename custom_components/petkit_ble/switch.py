"""Switch platform for Petkit BLE (power switch)."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SET_POWER_MODE
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity

_LOGGER = logging.getLogger(__name__)

POWER_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="power",
    translation_key="power",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petkit BLE switches from a config entry."""
    coordinator: PetkitBleCoordinator = config_entry.runtime_data
    async_add_entities([PetkitPowerSwitch(coordinator)])


class PetkitPowerSwitch(PetkitBleEntity, SwitchEntity):
    """Switch entity to toggle the fountain pump power."""

    def __init__(self, coordinator: PetkitBleCoordinator) -> None:
        """Initialise the power switch."""
        super().__init__(coordinator, POWER_SWITCH_DESCRIPTION.key)
        self.entity_description = POWER_SWITCH_DESCRIPTION

    @property
    def is_on(self) -> bool | None:
        """Return True when the fountain is powered on."""
        if self.coordinator.data is None:
            return None
        return bool(self.coordinator.data.power_status)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the fountain on."""
        await self._set_power(1)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fountain off."""
        await self._set_power(0)

    async def _set_power(self, power_state: int) -> None:
        """Send CMD 220 with the desired power state, keeping the current mode."""
        # Use the last known mode; default to 1 (normal) if data is absent or mode is invalid.
        raw_mode = self.coordinator.data.mode if self.coordinator.data else 1
        mode = raw_mode if raw_mode in (1, 2) else 1

        success = await self.coordinator.async_send_command(CMD_SET_POWER_MODE, [power_state, mode])
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set power state to %d", power_state)
