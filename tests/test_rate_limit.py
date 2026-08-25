"""Tests for the globally shared request budget."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.myip_wtf.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_requests_are_spaced_globally() -> None:
    """Two IP versions share one budget instead of getting one each."""
    limiter = RateLimiter(min_spacing=0.3)
    stamps: list[float] = []

    async def request() -> None:
        async with limiter:
            stamps.append(asyncio.get_running_loop().time())

    await asyncio.gather(request(), request(), request())

    assert len(stamps) == 3
    assert stamps[1] - stamps[0] >= 0.3
    assert stamps[2] - stamps[1] >= 0.3


@pytest.mark.asyncio
async def test_penalty_survives_slot_booking() -> None:
    """A 429 penalty is never shortened by the regular spacing."""
    limiter = RateLimiter(min_spacing=0.1)

    async with limiter:
        limiter.async_penalise(120)

    assert limiter.time_until_slot() > 100


@pytest.mark.asyncio
async def test_first_request_is_immediate() -> None:
    """The very first request does not wait for a slot."""
    limiter = RateLimiter(min_spacing=60)
    start = asyncio.get_running_loop().time()

    async with limiter:
        pass

    assert asyncio.get_running_loop().time() - start < 0.1
