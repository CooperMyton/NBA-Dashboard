"""Redis client factory (async), used for caching and rate limiting."""

from redis.asyncio import Redis

from backend.app.core.config import get_settings


def get_redis() -> Redis:
    """Return an async Redis client built from settings.

    Callers own the connection lifecycle; use ``async with get_redis() as r:`` or close
    explicitly with ``await r.aclose()``.
    """
    settings = get_settings()
    return Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
