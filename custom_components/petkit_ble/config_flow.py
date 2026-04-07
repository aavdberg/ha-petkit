"""Config flow for Petkit BLE integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import (
    ALIAS_CTW2,
    ALIAS_CTW3,
    ALIAS_W4X,
    ALIAS_W4XUVC,
    ALIAS_W5,
    ALIAS_W5C,
    ALIAS_W5N,
    CONF_MODEL,
    CONF_NAME,
    DOMAIN,
    PETKIT_NAME_PREFIXES,
)

_LOGGER = logging.getLogger(__name__)


def _get_alias_from_name(name: str) -> str:
    """Derive the device alias from its BLE advertisement name."""
    if "CTW3" in name:
        return ALIAS_CTW3
    if "CTW2" in name:
        return ALIAS_CTW2
    if "W5C" in name:
        return ALIAS_W5C
    if "W5N" in name:
        return ALIAS_W5N
    if "W4XUVC" in name:
        return ALIAS_W4XUVC
    if "W4X" in name:
        return ALIAS_W4X
    if "W5" in name:
        return ALIAS_W5
    return name


def _is_petkit_device(name: str) -> bool:
    """Return True if the BLE name matches a known Petkit fountain prefix."""
    return any(name.startswith(prefix) for prefix in PETKIT_NAME_PREFIXES)


class PetkitBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Petkit BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._discovered_devices: dict[str, str] = {}  # address -> name
        self._bluetooth_info: BluetoothServiceInfoBleak | None = None

    # ------------------------------------------------------------------
    # Auto-discovery (HA calls this when manifest bluetooth matcher fires)
    # ------------------------------------------------------------------

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a Bluetooth discovery from HA's auto-discovery."""
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()

        self._bluetooth_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm auto-discovered Petkit fountain."""
        assert self._bluetooth_info is not None
        info = self._bluetooth_info

        if user_input is not None:
            alias = _get_alias_from_name(info.name)
            return self.async_create_entry(
                title=info.name,
                data={
                    CONF_ADDRESS: info.address.upper(),
                    CONF_NAME: info.name,
                    CONF_MODEL: alias,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": info.name, "address": info.address},
        )

    # ------------------------------------------------------------------
    # Manual / user-initiated flow
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Scan for nearby Petkit BLE devices and let the user pick one."""
        if user_input is not None:
            address: str = user_input[CONF_ADDRESS].strip().upper()
            name: str = user_input.get(CONF_NAME, address)

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            alias = _get_alias_from_name(name)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name,
                    CONF_MODEL: alias,
                },
            )

        # Collect Petkit devices visible in current BLE scan results
        discovered: dict[str, str] = {}  # address -> name
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            if _is_petkit_device(service_info.name):
                discovered[service_info.address.upper()] = service_info.name

        self._discovered_devices = discovered

        if discovered:
            # Show a selector with discovered devices
            options = {
                addr: f"{name} ({addr})" for addr, name in discovered.items()
            }
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): vol.In(options),
                    }
                ),
            )

        # No devices found — fall back to manual MAC entry
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default=""): str,
                }
            ),
            errors={"base": "no_devices_found"},
        )
