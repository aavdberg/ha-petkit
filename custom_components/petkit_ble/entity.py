"""Base entity for Petkit BLE."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, CONF_MODEL, CONF_NAME, DOMAIN
from .coordinator import PetkitBleCoordinator


class PetkitBleEntity(CoordinatorEntity[PetkitBleCoordinator]):
    """Base class for all Petkit BLE entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PetkitBleCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        address: str = coordinator.config_entry.data[CONF_ADDRESS]
        mac_normalized = address.replace(":", "").lower()
        self._attr_unique_id = f"{mac_normalized}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=coordinator.config_entry.data[CONF_NAME],
            manufacturer="Petkit",
            model=coordinator.config_entry.data[CONF_MODEL],
        )

    @property
    def available(self) -> bool:
        """Return True when the coordinator last update succeeded."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
