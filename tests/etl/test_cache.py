"""Tests for prefix-based Redis cache invalidation (via fakeredis)."""

from fakeredis import FakeAsyncRedis

from backend.app.core.cache import invalidate_prefixes


async def test_invalidate_prefixes_removes_only_matching_keys() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    await redis.set("standings:2023:limit=25", "stale")
    await redis.set("teams:all", "stale")
    await redis.set("games:2023", "keep")

    deleted = await invalidate_prefixes(redis, ["standings:", "teams:"])

    assert deleted == 2
    assert await redis.get("standings:2023:limit=25") is None
    assert await redis.get("teams:all") is None
    assert await redis.get("games:2023") == "keep"
    await redis.aclose()
