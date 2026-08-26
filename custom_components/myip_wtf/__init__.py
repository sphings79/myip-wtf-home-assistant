"""The MyIP.wtf integration.

Reads the public IPv4/IPv6 address of this Home Assistant instance from the
free myip.wtf service and exposes it as sensors.

This is an unofficial, community built integration.  The myip.wtf /
wtfismyip.com service itself is operated by a third party - see the README for
credits and the upstream automation policy.
"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN, REPO
from .coordinator import MyIpWtfConfigEntry, MyIpWtfCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MyIpWtfConfigEntry) -> bool:
    """Set up MyIP.wtf from a config entry."""
    integration = async_get_loaded_integration(hass, entry.domain)
    coordinator = MyIpWtfCoordinator(hass, entry, str(integration.version), REPO)

    # Turning an IP version off in the options reloads the entry; drop the
    # device and entities of that version instead of leaving them behind as
    # unavailable leftovers.
    _async_remove_disabled_versions(hass, entry, coordinator.versions)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyIpWtfConfigEntry) -> bool:
    """Unload a config entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.async_clear_issues()
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: MyIpWtfConfigEntry) -> None:
    """Reload the config entry when its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: MyIpWtfConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow deleting a device whose IP version is no longer enabled."""
    return not (
        device.identifiers
        & _async_valid_identifiers(entry, entry.runtime_data.versions)
    )


@callback
def _async_valid_identifiers(
    entry: MyIpWtfConfigEntry, versions: list[str]
) -> set[tuple[str, str]]:
    """Return the device identifiers this entry currently provides."""
    return {(DOMAIN, f"{entry.entry_id}_{version}") for version in versions}


@callback
def _async_remove_disabled_versions(
    hass: HomeAssistant, entry: MyIpWtfConfigEntry, versions: list[str]
) -> None:
    """Remove devices of IP versions that are no longer enabled.

    Removing the device takes its entities with it, so no stale sensors are
    left in an unavailable state after the user turns a version off.
    """
    device_registry = dr.async_get(hass)
    valid = _async_valid_identifiers(entry, versions)

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.identifiers & valid:
            continue
        _LOGGER.debug(
            "Removing device %s, its IP version is no longer enabled", device.name
        )
        device_registry.async_update_device(
            device.id, remove_config_entry_id=entry.entry_id
        )
