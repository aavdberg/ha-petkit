"""Petkit BLE integration."""

from __future__ import annotations

import asyncio
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
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TIME,
]

_INTEGRATION_LOGGER = logging.getLogger(f"custom_components.{DOMAIN}")

# Track which config entries have debug enabled and a shared file handler.
_debug_entries: set[str] = set()
_file_handler: logging.Handler | None = None
# Serialise handler creation/teardown: ``_apply_debug_option`` is now async and
# has an ``await`` point (the executor job), so concurrent calls for multiple
# entries must not race on ``_file_handler``.
_debug_lock = asyncio.Lock()


def _build_file_handler(log_path: str) -> RotatingFileHandler:
    """Build the rotating file handler.

    ``RotatingFileHandler`` opens the log file in its constructor, which is
    blocking file I/O; this helper is always run in an executor so the open
    never happens on the event loop.
    """
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    return handler


async def _apply_debug_option(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply the debug option: set log level and manage the petkit.log file handler."""
    global _file_handler

    debug = entry.options.get(CONF_DEBUG, False)

    async with _debug_lock:
        if debug:
            _debug_entries.add(entry.entry_id)
        else:
            _debug_entries.discard(entry.entry_id)

        # Log level follows the union of all entries: DEBUG if any entry has it on.
        _INTEGRATION_LOGGER.setLevel(logging.DEBUG if _debug_entries else logging.NOTSET)

        if _debug_entries and _file_handler is None:
            log_path = os.path.join(hass.config.config_dir, "petkit.log")
            # Open the log file off the event loop to avoid a blocking open().
            handler = await hass.async_add_executor_job(_build_file_handler, log_path)
            _INTEGRATION_LOGGER.addHandler(handler)
            _file_handler = handler
            _LOGGER.debug("Debug log file opened: %s", log_path)

        elif not _debug_entries and _file_handler is not None:
            handler = _file_handler
            _INTEGRATION_LOGGER.removeHandler(handler)
            _file_handler = None
            # Closing flushes and closes the file — also blocking I/O.
            await hass.async_add_executor_job(handler.close)
            _LOGGER.info("Debug log file closed")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Petkit BLE from a config entry."""
    await _apply_debug_option(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    coordinator = PetkitBleCoordinator(hass, entry)
    await coordinator.async_load_persistent_state()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — re-apply debug level without full reload."""
    await _apply_debug_option(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Petkit BLE config entry."""
    # Clean up debug tracking for this entry so the file handler is removed
    # if no other entry still has debug enabled.
    _debug_entries.discard(entry.entry_id)
    await _apply_debug_option(hass, entry)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
