"""Diagnostics support for the MyIP.wtf integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import MyIpWtfConfigEntry

TO_REDACT = {"ip_address", "hostname", "location", "city"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MyIpWtfConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, with identifying data redacted."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "versions": coordinator.versions,
            "update_interval": str(coordinator.update_interval),
            "last_update_success": coordinator.last_update_success,
            "seconds_until_next_request_slot": round(
                coordinator.limiter.time_until_slot(), 1
            ),
            "ip_changed_at": {
                version: changed.isoformat() if changed else None
                for version, changed in coordinator.ip_changed_at.items()
            },
        },
        "data": {
            version: async_redact_data(asdict(info), TO_REDACT) if info else None
            for version, info in (coordinator.data or {}).items()
        },
    }
