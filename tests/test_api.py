"""Tests for the myip.wtf client."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientResponseError
import pytest

from custom_components.myip_wtf.api import (
    IpInfo,
    MyIpWtfClient,
    MyIpWtfConnectionError,
    MyIpWtfRateLimitError,
    MyIpWtfResponseError,
)
from custom_components.myip_wtf.rate_limit import RateLimiter, ResponseCache

PAYLOAD: dict[str, Any] = {
    "YourFuckingIPAddress": "203.0.113.7",
    "YourFuckingLocation": "Lemgo, NW, Germany",
    "YourFuckingHostname": "host.example.net",
    "YourFuckingISP": "Example ISP",
    "YourFuckingTorExit": False,
    "YourFuckingCity": "Lemgo",
    "YourFuckingCountry": "Germany",
    "YourFuckingCountryCode": "de",
}


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(self, status: int = 200, payload: Any = None, headers=None) -> None:
        self.status = status
        self._payload = PAYLOAD if payload is None else payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(None, (), status=self.status)

    async def json(self, content_type: str | None = None) -> Any:
        return self._payload

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class FakeSession:
    """Minimal aiohttp session stand-in."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(self, url: str, headers=None) -> Any:
        self.urls.append(url)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _client(
    responses: list[Any], spacing: float = 0.0, cache: ResponseCache | None = None
) -> MyIpWtfClient:
    return MyIpWtfClient(
        FakeSession(responses), RateLimiter(min_spacing=spacing), cache=cache
    )


def test_payload_is_mapped_to_neutral_fields() -> None:
    """The upstream field names are mapped onto readable attributes."""
    info = IpInfo.from_payload(PAYLOAD)

    assert info.ip_address == "203.0.113.7"
    assert info.hostname == "host.example.net"
    assert info.isp == "Example ISP"
    assert info.country_code == "DE"
    assert info.tor_exit is False


def test_blank_and_unknown_values_become_none() -> None:
    """Empty or placeholder values are normalised to None."""
    info = IpInfo.from_payload(
        {**PAYLOAD, "YourFuckingHostname": "  ", "YourFuckingCity": "unknown"}
    )

    assert info.hostname is None
    assert info.city is None


def test_missing_ip_address_is_rejected() -> None:
    """A response without an address is not usable."""
    with pytest.raises(MyIpWtfResponseError):
        IpInfo.from_payload({"YourFuckingIPAddress": ""})


@pytest.mark.asyncio
async def test_version_selects_the_matching_endpoint() -> None:
    """Each IP version has its own hostname."""
    client = _client([FakeResponse(), FakeResponse()])
    await client.async_get("ipv4")
    await client.async_get("ipv6")

    assert client._session.urls == [
        "https://ipv4.myip.wtf/json",
        "https://ipv6.myip.wtf/json",
    ]


@pytest.mark.asyncio
async def test_http_429_raises_and_penalises() -> None:
    """A rate limited answer backs the shared budget off."""
    limiter = RateLimiter(min_spacing=0.1)
    client = MyIpWtfClient(
        FakeSession([FakeResponse(status=429, headers={"Retry-After": "120"})]), limiter
    )

    with pytest.raises(MyIpWtfRateLimitError) as err:
        await client.async_get("ipv4")

    assert err.value.retry_after == 120.0
    assert limiter.time_until_slot() > 100


@pytest.mark.asyncio
async def test_transport_errors_are_wrapped() -> None:
    """Network failures surface as connection errors."""
    client = _client([ClientError("boom")])

    with pytest.raises(MyIpWtfConnectionError):
        await client.async_get("ipv6")


@pytest.mark.asyncio
async def test_server_errors_are_wrapped() -> None:
    """HTTP 5xx surfaces as a response error."""
    client = _client([FakeResponse(status=503)])

    with pytest.raises(MyIpWtfResponseError):
        await client.async_get("ipv4")


@pytest.mark.asyncio
async def test_non_object_payload_is_rejected() -> None:
    """A JSON array is not a valid answer."""
    client = _client([FakeResponse(payload=[1, 2, 3])])

    with pytest.raises(MyIpWtfResponseError):
        await client.async_get("ipv4")


@pytest.mark.asyncio
async def test_fresh_cache_entry_skips_the_request() -> None:
    """A config flow probe and the first refresh must not both hit the API."""
    client = _client([FakeResponse()], cache=ResponseCache(ttl=60))

    first = await client.async_get("ipv4")
    second = await client.async_get("ipv4")

    assert first == second
    assert client._session.urls == ["https://ipv4.myip.wtf/json"]


@pytest.mark.asyncio
async def test_stale_cache_entry_is_refetched() -> None:
    """Once the entry is older than the TTL, the service is asked again."""
    client = _client([FakeResponse(), FakeResponse()], cache=ResponseCache(ttl=0.05))

    await client.async_get("ipv4")
    await asyncio.sleep(0.1)
    await client.async_get("ipv4")

    assert len(client._session.urls) == 2


@pytest.mark.asyncio
async def test_cache_is_per_ip_version() -> None:
    """An IPv4 answer never satisfies an IPv6 request."""
    client = _client([FakeResponse(), FakeResponse()], cache=ResponseCache(ttl=60))

    await client.async_get("ipv4")
    await client.async_get("ipv6")

    assert len(client._session.urls) == 2
