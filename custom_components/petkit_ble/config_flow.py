"""Config flow for Petkit BLE integration."""

from __future__ import annotations

import logging
import secrets
from typing import Any

import voluptuous as vol
from bleak.exc import BleakCharacteristicNotFoundError
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .ble_client import PetkitBleClient
from .const import (
    ALIAS_CTW2,
    ALIAS_CTW3,
    ALIAS_W4X,
    ALIAS_W4XUVC,
    ALIAS_W5,
    ALIAS_W5C,
    ALIAS_W5N,
    CONF_DEBUG,
    CONF_DEVICE_SECRET,
    CONF_MODEL,
    CONF_NAME,
    DOMAIN,
    PETKIT_NAME_PREFIXES,
)

_LOGGER = logging.getLogger(__name__)


def _get_alias_from_name(name: str) -> str:
    """Derive the device alias from its BLE advertisement name.

    Returns one of the known ``ALIAS_*`` constants when the BLE name contains
    a recognisable model token. Returns an empty string when no model can be
    determined — for example when the proxy advert delivered no local name
    and the user only provided the MAC. The runtime then self-heals the alias
    on the first successful poll based on the CMD 210 payload length.
    """
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
    return ""


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
        self._pending_data: dict[str, Any] = {}  # data waiting for init
        self._repair_device_id: int = 0  # existing id of a device awaiting re-pair

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return PetkitBleOptionsFlow()

    # ------------------------------------------------------------------
    # Auto-discovery (HA calls this when manifest bluetooth matcher fires)
    # ------------------------------------------------------------------

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        """Handle a Bluetooth discovery from HA's auto-discovery."""
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()

        self._bluetooth_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm auto-discovered Petkit fountain."""
        assert self._bluetooth_info is not None
        info = self._bluetooth_info

        if user_input is not None:
            alias = _get_alias_from_name(info.name)
            self._pending_data = {
                CONF_ADDRESS: info.address.upper(),
                CONF_NAME: info.name,
                CONF_MODEL: alias,
            }
            return await self.async_step_init_device()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": info.name, "address": info.address},
        )

    # ------------------------------------------------------------------
    # Manual / user-initiated flow
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Scan for nearby Petkit BLE devices and let the user pick one."""
        if user_input is not None:
            address: str = user_input[CONF_ADDRESS].strip().upper()
            # Prefer an explicitly entered name, then the discovered BLE name
            # (the selector only submits the address), then the MAC as a last
            # resort. Using the BLE name keeps pinned entity IDs and model
            # detection based on e.g. "Petkit_CTW3_100" rather than the MAC.
            name: str = user_input.get(CONF_NAME, "").strip() or self._discovered_devices.get(address, "") or address

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            alias = _get_alias_from_name(name)
            self._pending_data = {
                CONF_ADDRESS: address,
                CONF_NAME: name,
                CONF_MODEL: alias,
            }
            return await self.async_step_init_device()

        # Collect Petkit devices visible in current BLE scan results
        discovered: dict[str, str] = {}  # address -> name
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            if _is_petkit_device(service_info.name):
                discovered[service_info.address.upper()] = service_info.name

        self._discovered_devices = discovered

        if discovered:
            # Show a selector with discovered devices
            options = {addr: f"{name} ({addr})" for addr, name in discovered.items()}
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

    # ------------------------------------------------------------------
    # Device initialization
    # ------------------------------------------------------------------

    async def async_step_init_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Check init status, then register a secret or offer re-pair recovery."""
        address = self._pending_data[CONF_ADDRESS]
        name = self._pending_data[CONF_NAME]

        ble_device = async_ble_device_from_address(self.hass, address, connectable=True)
        if ble_device is None:
            # Device not reachable — create entry without secret (legacy mode)
            _LOGGER.warning("Device %s not reachable for init, creating entry without secret", name)
            return self.async_create_entry(title=name, data=self._pending_data)

        client = PetkitBleClient(ble_device)
        try:
            initialized, device_id = await client.async_check_initialized()
        except BleakCharacteristicNotFoundError as err:
            _LOGGER.warning("Device %s does not have required BLE characteristics: %s", name, err)
            return self.async_abort(reason="unsupported_device")
        except Exception:
            _LOGGER.exception("Failed to check device init status for %s", name)
            # Cannot check — create entry without secret
            return self.async_create_entry(title=name, data=self._pending_data)

        if initialized:
            # Device already bound (typically by the Petkit app). The firmware
            # accepts a fresh CMD 73 init without a factory reset, so offer a
            # re-pair recovery step instead of dead-ending the flow (issue #75).
            self._repair_device_id = device_id
            return await self.async_step_confirm_repair()

        # Uninitialised — register a fresh secret straight away.
        secret_hex = await self._async_init_with_secret(address, device_id)
        if secret_hex is None:
            return self.async_show_form(
                step_id="init_device",
                description_placeholders={"name": name},
                errors={"base": "init_failed"},
            )
        return self.async_create_entry(title=name, data={**self._pending_data, CONF_DEVICE_SECRET: secret_hex})

    async def async_step_confirm_repair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user re-pair an already-bound device or cancel."""
        return self.async_show_menu(
            step_id="confirm_repair",
            menu_options=["repair_confirm", "repair_cancel"],
            description_placeholders={"name": self._pending_data[CONF_NAME]},
        )

    async def async_step_repair_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Re-pair the device with a fresh secret, overwriting the old pairing."""
        name = self._pending_data[CONF_NAME]
        secret_hex = await self._async_init_with_secret(self._pending_data[CONF_ADDRESS], self._repair_device_id)
        if secret_hex is None:
            return self.async_abort(reason="repair_failed")
        return self.async_create_entry(title=name, data={**self._pending_data, CONF_DEVICE_SECRET: secret_hex})

    async def async_step_repair_cancel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Abort the flow, leaving the already-paired device untouched."""
        return self.async_abort(reason="repair_cancelled")

    async def _async_init_with_secret(self, address: str, device_id: int) -> str | None:
        """Register a fresh secret with the device.

        Returns the secret as hex on success, or ``None`` if the device is
        unreachable or initialization fails.
        """
        secret = secrets.token_bytes(8)
        ble_device = async_ble_device_from_address(self.hass, address, connectable=True)
        if ble_device is None:
            return None

        try:
            success = await PetkitBleClient(ble_device).async_init_device(device_id, secret)
        except Exception:
            _LOGGER.exception("Failed to initialize device %s", address)
            return None

        return secret.hex() if success else None


class PetkitBleOptionsFlow(OptionsFlow):
    """Handle options for Petkit BLE (e.g. enable debug logging)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show and handle the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Optional(CONF_DEBUG): bool}),
                self.config_entry.options or {CONF_DEBUG: False},
            ),
        )
