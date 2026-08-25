"""Sensor platform for the MyIP.wtf integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .api import IpInfo
from .const import VERSION_LABELS
from .coordinator import MyIpWtfConfigEntry, MyIpWtfCoordinator
from .entity import MyIpWtfEntity


@dataclass(frozen=True, kw_only=True)
class MyIpWtfSensorEntityDescription(SensorEntityDescription):
    """Describe a MyIP.wtf sensor."""

    value_fn: Callable[[IpInfo], StateType]


SENSORS: tuple[MyIpWtfSensorEntityDescription, ...] = (
    MyIpWtfSensorEntityDescription(
        key="ip_address",
        translation_key="ip_address",
        value_fn=lambda info: info.ip_address,
    ),
    MyIpWtfSensorEntityDescription(
        key="hostname",
        translation_key="hostname",
        value_fn=lambda info: info.hostname,
    ),
    MyIpWtfSensorEntityDescription(
        key="isp",
        translation_key="isp",
        value_fn=lambda info: info.isp,
    ),
    MyIpWtfSensorEntityDescription(
        key="location",
        translation_key="location",
        value_fn=lambda info: info.location,
    ),
    MyIpWtfSensorEntityDescription(
        key="city",
        translation_key="city",
        value_fn=lambda info: info.city,
    ),
    MyIpWtfSensorEntityDescription(
        key="country",
        translation_key="country",
        value_fn=lambda info: info.country,
    ),
    MyIpWtfSensorEntityDescription(
        key="country_code",
        translation_key="country_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.country_code,
    ),
)

CHANGED_AT = SensorEntityDescription(
    key="ip_changed_at",
    translation_key="ip_changed_at",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIpWtfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MyIP.wtf sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for version in coordinator.versions:
        entities.extend(
            MyIpWtfSensor(coordinator, version, description) for description in SENSORS
        )
        entities.append(MyIpWtfChangedAtSensor(coordinator, version, CHANGED_AT))
    async_add_entities(entities)


class MyIpWtfSensor(MyIpWtfEntity, SensorEntity):
    """A single value reported by myip.wtf."""

    entity_description: MyIpWtfSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the current value."""
        if (info := self.info) is None:
            return None
        return self.entity_description.value_fn(info)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the IP version this sensor belongs to."""
        return {"ip_version": VERSION_LABELS[self.version]}


class MyIpWtfChangedAtSensor(MyIpWtfEntity, RestoreSensor):
    """Timestamp of the last observed public IP address change."""

    def __init__(
        self,
        coordinator: MyIpWtfCoordinator,
        version: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, version, description)
        self._restored: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the previous timestamp across restarts."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is None:
            return
        if (restored := dt_util.parse_datetime(last_state.state)) is not None:
            self._restored = restored

    @property
    def available(self) -> bool:
        """Keep the timestamp available even while a version is unreachable."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> datetime | None:
        """Return when the address of this IP version last changed."""
        return self.coordinator.ip_changed_at.get(self.version) or self._restored
