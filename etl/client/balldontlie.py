"""The single balldontlie.io client. Nothing else in the codebase calls the provider.

Responsibilities: auth header, token-bucket rate limiting (every request, retries included),
retry with exponential backoff on 429/5xx and transport errors, and cursor pagination.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.app.core.logging import get_logger
from etl.client.rate_limiter import TokenBucketRateLimiter

logger = get_logger("etl.client")

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


class BalldontlieClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        rate_limiter: TokenBucketRateLimiter,
        *,
        http_client: httpx.AsyncClient | None = None,
        max_attempts: int = 6,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._limiter = rate_limiter
        self._max_attempts = max_attempts
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def __aenter__(self) -> "BalldontlieClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=1, max=30),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                await self._limiter.acquire()
                response = await self._http.get(
                    url, params=params, headers={"Authorization": self._api_key}
                )
                if response.status_code in RETRYABLE_STATUS:
                    logger.warning(
                        "etl.client.retryable_status",
                        path=path,
                        status=response.status_code,
                    )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
                return payload
        raise RuntimeError("unreachable: AsyncRetrying always returns or raises")

    async def _paginate(self, path: str, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        page_base = dict(params)
        page_base.setdefault("per_page", 100)
        cursor: Any = None
        while True:
            page_params = dict(page_base)
            if cursor is not None:
                page_params["cursor"] = cursor
            payload = await self._request(path, page_params)
            for item in payload.get("data", []):
                yield item
            meta = payload.get("meta") or {}
            cursor = meta.get("next_cursor")
            if not cursor:
                break

    async def list_teams(self) -> list[dict[str, Any]]:
        return [team async for team in self._paginate("teams", {})]

    async def list_players(self) -> list[dict[str, Any]]:
        return [player async for player in self._paginate("players", {})]

    def iter_games(
        self,
        *,
        seasons: Sequence[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        params: dict[str, Any] = {}
        if seasons:
            params["seasons[]"] = list(seasons)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._paginate("games", params)
