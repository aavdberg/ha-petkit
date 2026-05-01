"""Switch platform for Petkit BLE (power, LED, DND, child lock)."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CMD_SET_POWER_MODE, CMD_WRITE_SETTINGS
from .coordinator import PetkitBleCoordinator
from .entity import PetkitBleEntity
from .protocol import build_change_mode_payload, build_ctw3_mode_payload, build_full_settings_payload

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
    async_add_entities(
        [
            PetkitPowerSwitch(coordinator),
            PetkitSettingsSwitch(coordinator, "led", "led_switch"),
            PetkitSettingsSwitch(coordinator, "do_not_disturb", "do_not_disturb_switch"),
            PetkitSettingsSwitch(coordinator, "child_lock", "is_locked"),
        ]
    )


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
        """Send CMD 220 with the desired power state.

        Per the reverse-engineered W5 protocol, CMD 220 byte[0] encodes power and mode:
        0=off, 1=normal (on), 2=smart (on). CTW3 uses [power, suspend, mode] (3 bytes).
        """
        data = self.coordinator.data

        if data is not None and data.is_ctw3:
            # CTW3: [power, suspend, mode] via protocol helper.
            # suspend=1 activates the pump (normal mode); suspend=0 lets the
            # device's internal timer manage cycling (smart mode).
            raw_mode = data.mode if data.mode in (1, 2) else 1
            suspend = power_state if raw_mode == 1 else 0
            payload = build_ctw3_mode_payload(power_state, suspend, raw_mode)
        else:
            # Generic W5/CTW2: byte[0] encodes power+mode (0=off, 1=normal, 2=smart)
            if power_state == 0:
                payload = build_change_mode_payload(0)
            else:
                raw_mode = data.mode if data is not None and data.mode in (1, 2) else 1
                payload = build_change_mode_payload(raw_mode)

        success = await self.coordinator.async_send_command(CMD_SET_POWER_MODE, payload)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set power state to %d", power_state)


class PetkitSettingsSwitch(PetkitBleEntity, SwitchEntity):
    """Switch entity for a boolean setting (LED, DND, child lock) via CMD 221."""

    def __init__(self, coordinator: PetkitBleCoordinator, key: str, field_name: str) -> None:
        """Initialise the settings switch."""
        super().__init__(coordinator, key)
        self.entity_description = SwitchEntityDescription(key=key, translation_key=key)
        self._field_name = field_name

    @property
    def is_on(self) -> bool | None:
        """Return True when the setting is enabled."""
        if self.coordinator.data is None:
            return None
        return bool(getattr(self.coordinator.data, self._field_name, 0))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the setting."""
        await self._set_value(1)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the setting."""
        await self._set_value(0)

    async def _set_value(self, value: int) -> None:
        """Send CMD 221 with updated settings."""
        data = self.coordinator.data
        if data is None:
            return
        payload = build_full_settings_payload(data, **{self._field_name: value})
        success = await self.coordinator.async_send_command(CMD_WRITE_SETTINGS, payload)
        if success:
            # Optimistically update local state. Some firmware revisions
            # never reply to CMD 211, so the next poll won't refresh this
            # field — without this update the UI would flip back to the
            # stale cached value.
            setattr(data, self._field_name, value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %d", self._field_name, value)
