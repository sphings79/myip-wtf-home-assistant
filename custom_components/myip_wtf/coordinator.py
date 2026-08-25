"""Data update coordinator for the MyIP.wtf integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    USER_AGENT,
    IpInfo,
    MyIpWtfClient,
    MyIpWtfError,
    MyIpWtfRateLimitError,
)
from .const import (
    CONF_IPV4,
    CONF_IPV6,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_IP_CHANGED,
    FAILURE_THRESHOLD,
    IPV4,
    IPV6,
    ISSUE_RATE_LIMITED,
    ISSUE_VERSION_UNAVAILABLE,
    VERSION_LABELS,
)
from .rate_limit import async_get_cache, async_get_limiter

_LOGGER = logging.getLogger(__name__)

type MyIpWtfConfigEntry = ConfigEntry[MyIpWtfCoordinator]


class MyIpWtfCoordinator(DataUpdateCoordinator[dict[str, IpInfo | None]]):
    """Poll myip.wtf for the public IP addresses of this Home Assistant host."""

    config_entry: MyIpWtfConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MyIpWtfConfigEntry,
        integration_version: str,
        repo: str,
    ) -> None:
        """Initialise the coordinator from the config entry options."""
        options = {**entry.data, **entry.options}
        self.versions: list[str] = [
            version
            for version, key in ((IPV4, CONF_IPV4), (IPV6, CONF_IPV6))
            if options.get(key, version == IPV4)
        ]
        interval = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=interval),
        )

        self.limiter = async_get_limiter(hass)
        self.client = MyIpWtfClient(
            async_get_clientsession(hass),
            self.limiter,
            USER_AGENT.format(version=integration_version, repo=repo),
            async_get_cache(hass),
        )
        # The very first refresh only fetches one IP version so Home Assistant
        # does not have to wait a full rate limit window during startup.  The
        # remaining versions are picked up by a one-off catch-up refresh.
        self._startup = True
        self._catch_up: list[str] = []
        self._repo = repo
        self.ip_changed_at: dict[str, datetime | None] = dict.fromkeys(self.versions)
        self._failures: dict[str, int] = dict.fromkeys(self.versions, 0)
        # Last answer that actually arrived, per IP version.  Kept separately
        # from self.data so a temporary outage cannot hide a change that
        # happened while the service was unreachable.
        self._last_seen: dict[str, IpInfo] = {}

    async def _async_update_data(self) -> dict[str, IpInfo | None]:
        """Fetch every enabled IP version, one request at a time.

        Requests are serialised by the globally shared rate limiter, so with
        both IP versions enabled a refresh cycle spans at least one minute.
        """
        # Start from every enabled version so consumers can rely on the keys,
        # then carry over values for versions this cycle does not refetch.
        result: dict[str, IpInfo | None] = dict.fromkeys(self.versions)
        result.update(self.data or {})
        errors: list[str] = []
        rate_limited = False

        versions = self.versions
        if self._startup:
            self._startup = False
            versions = self.versions[:1]
            self._catch_up = self.versions[1:]
            if self._catch_up:
                self._async_schedule_catch_up()
        elif self._catch_up:
            versions = self._catch_up
            self._catch_up = []

        for version in versions:
            try:
                info = await self.client.async_get(version)
            except MyIpWtfRateLimitError as err:
                _LOGGER.warning("myip.wtf rate limited the %s request", version)
                rate_limited = True
                result[version] = self._last_seen.get(version)
                errors.append(str(err))
                continue
            except MyIpWtfError as err:
                self._failures[version] = self._failures.get(version, 0) + 1
                _LOGGER.debug(
                    "Update for %s failed (%s consecutive): %s",
                    version,
                    self._failures[version],
                    err,
                )
                self._async_set_version_issue(
                    version, self._failures[version] >= FAILURE_THRESHOLD
                )
                result[version] = None
                errors.append(str(err))
                continue

            self._failures[version] = 0
            self._async_set_version_issue(version, False)
            result[version] = info
            self._async_handle_change(version, self._last_seen.get(version), info)
            self._last_seen[version] = info

        self._async_set_rate_limit_issue(rate_limited)

        # Only give up when no enabled IP version has usable data at all - a
        # failing IPv6 must not pull the working IPv4 entities down with it.
        if errors and all(result.get(version) is None for version in self.versions):
            raise UpdateFailed("; ".join(errors))

        return result

    def _async_schedule_catch_up(self) -> None:
        """Refresh again once the next request slot is available."""

        async def _catch_up(_now) -> None:
            await self.async_request_refresh()

        self.config_entry.async_on_unload(
            async_call_later(self.hass, self.limiter.min_spacing + 5, _catch_up)
        )

    def _async_handle_change(
        self, version: str, old: IpInfo | None, new: IpInfo
    ) -> None:
        """Fire an event when the public IP address of a version changed."""
        if old is None or old.ip_address == new.ip_address:
            if self.ip_changed_at.get(version) is None and old is None:
                # First successful poll - remember when we learned the address.
                self.ip_changed_at[version] = dt_util.utcnow()
            return

        self.ip_changed_at[version] = dt_util.utcnow()
        _LOGGER.info(
            "Public %s address changed from %s to %s",
            VERSION_LABELS[version],
            old.ip_address,
            new.ip_address,
        )
        self.hass.bus.async_fire(
            EVENT_IP_CHANGED,
            {
                "entry_id": self.config_entry.entry_id,
                "ip_version": version,
                "old_ip": old.ip_address,
                "new_ip": new.ip_address,
                "hostname": new.hostname,
                "isp": new.isp,
                "country": new.country,
                "country_code": new.country_code,
                "city": new.city,
                "tor_exit": new.tor_exit,
            },
        )

    def _async_set_rate_limit_issue(self, active: bool) -> None:
        """Create or clear the repair issue about upstream rate limiting."""
        if active:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_RATE_LIMITED,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_RATE_LIMITED,
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_RATE_LIMITED)

    def _async_set_version_issue(self, version: str, active: bool) -> None:
        """Create or clear the repair issue for a permanently failing version."""
        issue_id = ISSUE_VERSION_UNAVAILABLE.format(version=version)
        if active:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="version_unavailable",
                translation_placeholders={"version": VERSION_LABELS[version]},
                learn_more_url=f"https://github.com/{self._repo}#troubleshooting",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def async_clear_issues(self) -> None:
        """Remove every repair issue owned by this entry."""
        self._async_set_rate_limit_issue(False)
        for version in self.versions:
            self._async_set_version_issue(version, False)
