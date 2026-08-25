"""The MyIP.wtf integration.

Reads the public IPv4/IPv6 address of this Home Assistant instance from the
free myip.wtf service and exposes it as sensors.

This is an unofficial, community built integration.  The myip.wtf /
wtfismyip.com service itself is operated by a third party - see the README for
credits and the upstream automation policy.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_loaded_integration

from .const import REPO
from .coordinator import MyIpWtfConfigEntry, MyIpWtfCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MyIpWtfConfigEntry) -> bool:
    """Set up MyIP.wtf from a config entry."""
    integration = async_get_loaded_integration(hass, entry.domain)
    coordinator = MyIpWtfCoordinator(hass, entry, str(integration.version), REPO)
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
