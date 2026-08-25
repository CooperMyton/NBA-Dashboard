"""Redis-backed sliding-window rate limiter (spec: 60 req/min/IP on public GETs).

Uses a sorted set of request timestamps per identifier: expired entries are trimmed, the
current request is recorded, and the window count is compared to the limit. ``now_ms`` is
injectable for deterministic tests.
"""

import time
import uuid

from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis,
    identifier: str,
    *,
    limit: int,
    window_s: int,
    now_ms: int | None = None,
) -> bool:
    """Record a request and return whether it is within the limit for the window."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    key = f"ratelimit:{identifier}"
    window_start = now_ms - window_s * 1000
    member = f"{now_ms}:{uuid.uuid4().hex}"

    async with redis.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {member: now_ms})
        pipe.zcard(key)
        pipe.expire(key, window_s)
        results = await pipe.execute()

    count = int(results[2])
    return count <= limit
