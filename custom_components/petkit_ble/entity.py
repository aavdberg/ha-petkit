"""Base entity for Petkit BLE."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, CONF_MODEL, CONF_NAME, DOMAIN
from .coordinator import PetkitBleCoordinator


class PetkitBleEntity(CoordinatorEntity[PetkitBleCoordinator]):
    """Base class for all Petkit BLE entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PetkitBleCoordinator,
        key: str,
        entity_id_format: str | None = None,
    ) -> None:
        """Initialise the entity.

        When ``entity_id_format`` is provided, the ``entity_id`` is pinned to a
        stable, language-independent value of the form
        ``<platform>.<slug(device_name)>_<key>`` (e.g.
        ``sensor.petkit_ctw3_100_filter_percent``). The friendly name shown in
        the UI is still localized via ``translation_key``; only the entity_id is
        forced to English so shared dashboards remain portable across languages.
        """
        super().__init__(coordinator)
        address: str = coordinator.config_entry.data[CONF_ADDRESS]
        mac_normalized = address.replace(":", "").lower()
        self._attr_unique_id = f"{mac_normalized}_{key}"
        self._address = address

        if entity_id_format is not None:
            device_name: str = coordinator.config_entry.data[CONF_NAME]
            self.entity_id = async_generate_entity_id(
                entity_id_format,
                f"{device_name}_{key}",
                hass=coordinator.hass,
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info, including firmware version when available."""
        d = self.coordinator.data
        firmware = d.firmware if d else None
        hardware = d.hardware_version if d else None
        serial = d.serial_number if d else None
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=self.coordinator.config_entry.data[CONF_NAME],
            manufacturer="Petkit",
            model=self.coordinator.config_entry.data[CONF_MODEL],
            sw_version=firmware or None,
            hw_version=hardware or None,
            serial_number=serial or None,
        )

    @property
    def available(self) -> bool:
        """Return True when the coordinator last update succeeded."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
