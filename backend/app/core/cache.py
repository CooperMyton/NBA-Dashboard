"""Redis cache: key conventions, prefix invalidation, and a read-through helper.

Keys live under stable prefixes so ETL can invalidate a whole family after a load and the API
can build read-through keys under the same prefixes — centralized here so the two processes
never disagree on key shape (docs/decisions.md D-009).
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from redis.asyncio import Redis

TEAMS_PREFIX = "teams:"
STANDINGS_PREFIX = "standings:"
PREDICTIONS_PREFIX = "predictions:"
PROJECTIONS_PREFIX = "projections:"


async def invalidate_prefixes(redis: Redis, prefixes: Sequence[str]) -> int:
    """Delete every key under each prefix. Returns the number of keys removed."""
    deleted = 0
    for prefix in prefixes:
        keys = [key async for key in redis.scan_iter(match=f"{prefix}*")]
        if keys:
            deleted += await redis.delete(*keys)
    return deleted


async def cached_json(
    redis: Redis, key: str, ttl_s: int, producer: Callable[[], Awaitable[Any]]
) -> Any:
    """Return the cached JSON for ``key``, else call ``producer``, cache, and return it."""
    cached = await redis.get(key)
    if cached is not None:
        return json.loads(cached)
    value = await producer()
    await redis.set(key, json.dumps(value), ex=ttl_s)
    return value
