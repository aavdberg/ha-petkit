"""Petkit BLE integration."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

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

# Track which config entries have debug enabled and a shared file handler.
_debug_entries: set[str] = set()
_file_handler: logging.Handler | None = None


def _apply_debug_option(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply the debug option: set log level and manage the petkit.log file handler."""
    global _file_handler

    debug = entry.options.get(CONF_DEBUG, False)

    if debug:
        _debug_entries.add(entry.entry_id)
    else:
        _debug_entries.discard(entry.entry_id)

    # Log level follows the union of all entries: DEBUG if any entry has it on.
    _INTEGRATION_LOGGER.setLevel(logging.DEBUG if _debug_entries else logging.NOTSET)

    if _debug_entries and _file_handler is None:
        log_path = os.path.join(hass.config.config_dir, "petkit.log")
        handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        _INTEGRATION_LOGGER.addHandler(handler)
        _file_handler = handler
        _LOGGER.debug("Debug log file opened: %s", log_path)

    elif not _debug_entries and _file_handler is not None:
        _INTEGRATION_LOGGER.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
        _LOGGER.info("Debug log file closed")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Petkit BLE from a config entry."""
    _apply_debug_option(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    coordinator = PetkitBleCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — re-apply debug level without full reload."""
    _apply_debug_option(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Petkit BLE config entry."""
    # Clean up debug tracking for this entry so the file handler is removed
    # if no other entry still has debug enabled.
    _debug_entries.discard(entry.entry_id)
    _apply_debug_option(hass, entry)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
