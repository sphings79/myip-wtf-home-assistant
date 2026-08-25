"""Small async client for the myip.wtf public IP service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any, cast

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import ENDPOINTS, REQUEST_TIMEOUT
from .rate_limit import RateLimiter, ResponseCache

_LOGGER = logging.getLogger(__name__)

#: Upstream JSON keys.  The service uses colourful field names; they are mapped
#: onto neutral attribute names right here so the rest of the integration never
#: has to deal with them.
_KEY_IP = "YourFuckingIPAddress"
_KEY_LOCATION = "YourFuckingLocation"
_KEY_HOSTNAME = "YourFuckingHostname"
_KEY_ISP = "YourFuckingISP"
_KEY_TOR_EXIT = "YourFuckingTorExit"
_KEY_CITY = "YourFuckingCity"
_KEY_COUNTRY = "YourFuckingCountry"
_KEY_COUNTRY_CODE = "YourFuckingCountryCode"

USER_AGENT = "HomeAssistant-myip_wtf/{version} (+https://github.com/{repo})"


class MyIpWtfError(Exception):
    """Base error for the myip.wtf client."""


class MyIpWtfConnectionError(MyIpWtfError):
    """The service could not be reached."""


class MyIpWtfRateLimitError(MyIpWtfError):
    """The service refused the request because of rate limiting."""

    def __init__(self, retry_after: float = 60.0) -> None:
        """Store how long the caller should back off."""
        super().__init__(f"Rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


class MyIpWtfResponseError(MyIpWtfError):
    """The service returned something we cannot use."""


def _clean(value: Any) -> str | None:
    """Return a stripped string, or None for empty/unknown values."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() in ("unknown", "none", "-"):
        return None
    return value


@dataclass(frozen=True, slots=True)
class IpInfo:
    """A single answer from the myip.wtf service."""

    ip_address: str
    hostname: str | None = None
    isp: str | None = None
    location: str | None = None
    city: str | None = None
    country: str | None = None
    country_code: str | None = None
    tor_exit: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> IpInfo:
        """Build an :class:`IpInfo` from the raw JSON payload."""
        if not (ip_address := _clean(payload.get(_KEY_IP))):
            raise MyIpWtfResponseError("Response did not contain an IP address")
        country_code = _clean(payload.get(_KEY_COUNTRY_CODE))
        return cls(
            ip_address=ip_address,
            hostname=_clean(payload.get(_KEY_HOSTNAME)),
            isp=_clean(payload.get(_KEY_ISP)),
            location=_clean(payload.get(_KEY_LOCATION)),
            city=_clean(payload.get(_KEY_CITY)),
            country=_clean(payload.get(_KEY_COUNTRY)),
            country_code=country_code.upper() if country_code else None,
            tor_exit=bool(payload.get(_KEY_TOR_EXIT, False)),
        )


class MyIpWtfClient:
    """Fetch public IP details, one request per minute at most."""

    def __init__(
        self,
        session: ClientSession,
        limiter: RateLimiter,
        user_agent: str | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._limiter = limiter
        self._cache = cache
        self._headers = {"Accept": "application/json"}
        if user_agent:
            self._headers["User-Agent"] = user_agent

    async def async_get(self, version: str) -> IpInfo:
        """Return the public IP details for ``ipv4`` or ``ipv6``.

        The call blocks until the shared rate limiter grants a slot, so it may
        take up to a minute to return - unless a fresh answer is still cached.
        """
        if self._cache is not None and (cached := self._cache.get(version)) is not None:
            _LOGGER.debug("Serving %s from the short lived response cache", version)
            return cast(IpInfo, cached)

        url = ENDPOINTS[version]
        async with self._limiter:
            _LOGGER.debug("Requesting %s", url)
            try:
                async with (
                    asyncio.timeout(REQUEST_TIMEOUT.total_seconds()),
                    self._session.get(url, headers=self._headers) as response,
                ):
                    if response.status == 429:
                        retry_after = _retry_after(response.headers.get("Retry-After"))
                        self._limiter.async_penalise(retry_after)
                        raise MyIpWtfRateLimitError(retry_after)
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except MyIpWtfError:
                raise
            except ClientResponseError as err:
                raise MyIpWtfResponseError(f"{url} returned HTTP {err.status}") from err
            except TimeoutError as err:
                # TimeoutError is a subclass of OSError, so it has to be caught
                # before the generic transport error branch below.
                raise MyIpWtfConnectionError(f"Timeout while reaching {url}") from err
            except (ClientError, OSError) as err:
                raise MyIpWtfConnectionError(f"Could not reach {url}: {err}") from err

        if not isinstance(payload, dict):
            raise MyIpWtfResponseError(f"{url} did not return a JSON object")

        info = IpInfo.from_payload(payload)
        if self._cache is not None:
            self._cache.set(version, info)
        return info


def _retry_after(header: str | None) -> float:
    """Parse a Retry-After header, falling back to a minute."""
    try:
        return max(60.0, float(header)) if header else 60.0
    except ValueError:
        return 60.0
