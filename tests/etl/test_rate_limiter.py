"""Tests for the provider token-bucket rate limiter."""

import asyncio

import pytest

from etl.client.rate_limiter import TokenBucketRateLimiter


async def test_initial_burst_up_to_capacity_is_immediate() -> None:
    limiter = TokenBucketRateLimiter(5)
    for _ in range(5):
        await asyncio.wait_for(limiter.acquire(), timeout=0.1)


async def test_blocks_once_capacity_is_exhausted() -> None:
    limiter = TokenBucketRateLimiter(5)
    for _ in range(5):
        await limiter.acquire()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire(), timeout=0.1)


async def test_refills_over_time() -> None:
    clock = {"t": 0.0}
    limiter = TokenBucketRateLimiter(60, time_func=lambda: clock["t"])  # 1 token/sec
    for _ in range(60):
        await limiter.acquire()
    assert limiter.available_tokens < 1
    clock["t"] = 2.0  # two seconds pass -> ~2 tokens
    assert limiter.available_tokens >= 2


def test_rejects_nonpositive_rate() -> None:
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(0)


async def test_provider_limiter_is_burst_free() -> None:
    from etl.client.rate_limiter import make_provider_limiter

    limiter = make_provider_limiter(5)  # -> rate 4, capacity 1
    # Exactly one token of burst, then it must throttle (no 5-at-once burst).
    await asyncio.wait_for(limiter.acquire(), timeout=0.1)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire(), timeout=0.1)
