"""Async token-bucket rate limiter for the single provider client.

balldontlie Free tier allows 5 requests/minute; every provider call acquires a token
before going out. The limiter is deliberately provider-agnostic and fully unit-tested.
"""

import asyncio
import time
from collections.abc import Callable


class TokenBucketRateLimiter:
    """Token bucket that refills continuously at ``rate_per_minute`` tokens/minute.

    ``acquire()`` returns immediately when a token is available, otherwise sleeps just long
    enough for the next token to accrue. Capacity equals ``rate_per_minute`` (one minute of
    burst).
    """

    def __init__(
        self,
        rate_per_minute: int,
        *,
        capacity: int | None = None,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        # Capacity defaults to the rate (one minute of burst). Pass capacity=1 for a burst-free,
        # evenly-spaced limiter suited to hard provider caps.
        bucket = rate_per_minute if capacity is None else capacity
        if bucket <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = float(bucket)
        self._tokens = float(bucket)
        self._refill_per_sec = rate_per_minute / 60.0
        self._time = time_func
        self._updated = time_func()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._time()
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_sec)
            self._updated = now

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens

    async def acquire(self) -> None:
        """Block until a token is available, then consume it."""
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_s = (1 - self._tokens) / self._refill_per_sec
                await asyncio.sleep(wait_s)


def make_provider_limiter(provider_limit_per_min: int) -> TokenBucketRateLimiter:
    """Build a burst-free limiter that stays safely under a hard provider cap.

    A token bucket with ``capacity == rate`` can emit up to ~2x the rate in the first minute
    (initial burst + refill), which trips hard caps like balldontlie's 5/min. Using capacity 1
    removes the burst, and we request one under the cap for rolling-window headroom.
    """
    safe_rate = max(1, provider_limit_per_min - 1)
    return TokenBucketRateLimiter(safe_rate, capacity=1)
