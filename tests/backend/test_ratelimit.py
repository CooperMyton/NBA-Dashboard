"""Unit tests for the sliding-window rate limiter."""

from fakeredis import FakeAsyncRedis

from backend.app.core.ratelimit import check_rate_limit


async def test_blocks_after_limit_then_resets_after_window() -> None:
    redis = FakeAsyncRedis()
    now = 1_000_000

    for _ in range(3):
        assert await check_rate_limit(redis, "ip", limit=3, window_s=60, now_ms=now) is True

    # 4th within the same window is blocked.
    assert await check_rate_limit(redis, "ip", limit=3, window_s=60, now_ms=now) is False

    # After the window slides past the old entries, requests are allowed again.
    assert await check_rate_limit(redis, "ip", limit=3, window_s=60, now_ms=now + 61_000) is True

    await redis.aclose()


async def test_separate_identifiers_have_independent_windows() -> None:
    redis = FakeAsyncRedis()
    now = 2_000_000
    assert await check_rate_limit(redis, "a", limit=1, window_s=60, now_ms=now) is True
    assert await check_rate_limit(redis, "a", limit=1, window_s=60, now_ms=now) is False
    assert await check_rate_limit(redis, "b", limit=1, window_s=60, now_ms=now) is True
    await redis.aclose()
