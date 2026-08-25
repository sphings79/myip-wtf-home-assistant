"""A globally shared request budget for the MyIP.wtf integration.

The upstream automation policy asks for at most one request per minute.  The
budget is enforced here in one place: every outbound request - no matter which
IP version, coordinator or config entry triggered it - has to pass through the
same :class:`RateLimiter` instance, so two enabled IP versions still add up to
one request per minute rather than one each.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, callback

from .const import DATA_CACHE, DATA_LIMITER, DOMAIN, MIN_REQUEST_SPACING

_LOGGER = logging.getLogger(__name__)


class RateLimiter:
    """Serialise requests and keep a minimum spacing between them."""

    def __init__(self, min_spacing: float = MIN_REQUEST_SPACING) -> None:
        """Initialise the limiter."""
        self._min_spacing = min_spacing
        self._lock = asyncio.Lock()
        self._next_slot: float | None = None

    @property
    def min_spacing(self) -> float:
        """Return the enforced spacing between two requests in seconds."""
        return self._min_spacing

    def time_until_slot(self) -> float:
        """Return the seconds left until the next request may be sent."""
        if self._next_slot is None:
            return 0.0
        return max(0.0, self._next_slot - asyncio.get_running_loop().time())

    async def __aenter__(self) -> RateLimiter:
        """Wait for a free slot and claim it."""
        await self._lock.acquire()
        loop = asyncio.get_running_loop()
        if self._next_slot is not None and (wait := self._next_slot - loop.time()) > 0:
            _LOGGER.debug("Holding request for %.1fs to honour the rate limit", wait)
            try:
                await asyncio.sleep(wait)
            except asyncio.CancelledError:
                self._lock.release()
                raise
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Book the next free slot and release the lock.

        A penalty booked during the request (e.g. after an HTTP 429) always
        wins over the regular spacing.
        """
        next_slot = asyncio.get_running_loop().time() + self._min_spacing
        self._next_slot = max(self._next_slot or 0.0, next_slot)
        self._lock.release()

    @callback
    def async_penalise(self, seconds: float) -> None:
        """Push the next free slot further out, e.g. after an HTTP 429."""
        loop = asyncio.get_running_loop()
        self._next_slot = max(self._next_slot or 0.0, loop.time() + seconds)


@callback
def async_get_limiter(hass: HomeAssistant) -> RateLimiter:
    """Return the limiter shared by every MyIP.wtf request in this instance."""
    domain_data: dict = hass.data.setdefault(DOMAIN, {})
    if (limiter := domain_data.get(DATA_LIMITER)) is None:
        limiter = domain_data[DATA_LIMITER] = RateLimiter()
    return limiter


class ResponseCache:
    """Remember answers for as long as a request slot is blocked anyway.

    Without it a config flow probe and the first refresh right after it would
    ask for the same IP version twice, and the second call would have to sit
    out a full rate limit window before Home Assistant finished setting the
    entry up.
    """

    def __init__(self, ttl: float = MIN_REQUEST_SPACING) -> None:
        """Initialise the cache."""
        self._ttl = ttl
        self._entries: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        """Return a cached answer that is still fresh, if any."""
        if (entry := self._entries.get(key)) is None:
            return None
        stored_at, value = entry
        if asyncio.get_running_loop().time() - stored_at > self._ttl:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: object) -> None:
        """Store an answer."""
        self._entries[key] = (asyncio.get_running_loop().time(), value)


@callback
def async_get_cache(hass: HomeAssistant) -> ResponseCache:
    """Return the response cache shared by every MyIP.wtf client."""
    domain_data: dict = hass.data.setdefault(DOMAIN, {})
    if (cache := domain_data.get(DATA_CACHE)) is None:
        cache = domain_data[DATA_CACHE] = ResponseCache()
    return cache
