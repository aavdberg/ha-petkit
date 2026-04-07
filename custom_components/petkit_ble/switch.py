"""Switch platform for Petkit BLE (power switch)."""

from __future__ import annotations

import logging

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble_client import PetkitBleClient
from .const import CMD_SET_POWER_MODE, CONF_ADDRESS, CONF_MODEL
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
        address: str = self.coordinator.config_entry.data[CONF_ADDRESS]
        alias: str = self.coordinator.config_entry.data[CONF_MODEL]
        mode = self.coordinator.data.mode if self.coordinator.data else 1

        ble_device = async_ble_device_from_address(self.coordinator.hass, address, connectable=True)
        if ble_device is None:
            _LOGGER.warning("Cannot set power: device %s not found", address)
            return

        client = PetkitBleClient(ble_device)
        success = await client.async_send_command(CMD_SET_POWER_MODE, [power_state, mode], alias)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set power state to %d for %s", power_state, address)
