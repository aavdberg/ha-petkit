"""Petkit BLE integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEBUG, DOMAIN
from .coordinator import PetkitBleCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]

_INTEGRATION_LOGGER = logging.getLogger(f"custom_components.{DOMAIN}")


def _apply_debug_option(entry: ConfigEntry) -> None:
    """Set log level based on the debug option."""
    debug = entry.options.get(CONF_DEBUG, False)
    _INTEGRATION_LOGGER.setLevel(logging.DEBUG if debug else logging.NOTSET)
    _LOGGER.debug("Debug logging %s", "enabled" if debug else "disabled")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Petkit BLE from a config entry."""
    _apply_debug_option(entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    coordinator = PetkitBleCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — re-apply debug level without full reload."""
    _apply_debug_option(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Petkit BLE config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
