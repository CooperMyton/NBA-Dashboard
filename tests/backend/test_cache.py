"""Unit tests for the read-through JSON cache helper."""

from typing import Any

from fakeredis import FakeAsyncRedis

from backend.app.core.cache import cached_json


async def test_cached_json_runs_producer_once() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    calls = {"n": 0}

    async def producer() -> dict[str, Any]:
        calls["n"] += 1
        return {"value": calls["n"]}

    first = await cached_json(redis, "k", 60, producer)
    second = await cached_json(redis, "k", 60, producer)

    assert first == {"value": 1}
    assert second == {"value": 1}  # served from cache, producer not re-run
    assert calls["n"] == 1
    await redis.aclose()
