"""Shared entity base class for the MyIP.wtf integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import IpInfo
from .const import DOMAIN, MANUFACTURER, VERSION_LABELS
from .coordinator import MyIpWtfCoordinator


class MyIpWtfEntity(CoordinatorEntity[MyIpWtfCoordinator]):
    """Base entity grouping all values of one IP version into one device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyIpWtfCoordinator,
        version: str,
        description: EntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.version = version
        entry_id = coordinator.config_entry.entry_id
        label = VERSION_LABELS[version]
        self._attr_unique_id = f"{entry_id}_{version}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{version}")},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=f"Public {label} address",
            name=f"MyIP.wtf {label}",
            configuration_url="https://myip.wtf/",
        )

    @property
    def info(self) -> IpInfo | None:
        """Return the latest answer for this IP version, if any."""
        return (self.coordinator.data or {}).get(self.version)

    @property
    def available(self) -> bool:
        """Return True when this IP version was reachable during the last poll."""
        return super().available and self.info is not None
