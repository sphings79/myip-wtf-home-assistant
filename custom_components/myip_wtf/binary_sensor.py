"""Binary sensor platform for the MyIP.wtf integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MyIpWtfConfigEntry
from .entity import MyIpWtfEntity

TOR_EXIT = BinarySensorEntityDescription(
    key="tor_exit",
    translation_key="tor_exit",
)

REACHABLE = BinarySensorEntityDescription(
    key="reachable",
    translation_key="reachable",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIpWtfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MyIP.wtf binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for version in coordinator.versions:
        entities.append(MyIpWtfTorExitSensor(coordinator, version, TOR_EXIT))
        entities.append(MyIpWtfReachableSensor(coordinator, version, REACHABLE))
    async_add_entities(entities)


class MyIpWtfTorExitSensor(MyIpWtfEntity, BinarySensorEntity):
    """Report whether the public address is a known Tor exit node."""

    @property
    def is_on(self) -> bool | None:
        """Return True when myip.wtf flags the address as a Tor exit node."""
        if (info := self.info) is None:
            return None
        return info.tor_exit


class MyIpWtfReachableSensor(MyIpWtfEntity, BinarySensorEntity):
    """Report whether this IP version reached myip.wtf during the last poll."""

    @property
    def available(self) -> bool:
        """Stay available so the off state can be reported."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True when the last poll for this IP version succeeded."""
        return self.info is not None
