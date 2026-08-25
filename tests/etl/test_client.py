"""Tests for BalldontlieClient: cursor pagination and retry-on-429, via a mock transport."""

import httpx

from etl.client.balldontlie import BalldontlieClient
from etl.client.rate_limiter import TokenBucketRateLimiter


def _client(handler: httpx.MockTransport) -> BalldontlieClient:
    http = httpx.AsyncClient(transport=handler)
    # High rate so the limiter never adds latency in tests.
    return BalldontlieClient(
        "test-key", "https://api.test/v1", TokenBucketRateLimiter(600), http_client=http
    )


async def test_paginates_across_cursors() -> None:
    pages = {
        None: {"data": [{"id": 1}, {"id": 2}], "meta": {"next_cursor": 99}},
        "99": {"data": [{"id": 3}], "meta": {"next_cursor": None}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "test-key"
        cursor = request.url.params.get("cursor")
        return httpx.Response(200, json=pages[cursor])

    client = _client(httpx.MockTransport(handler))
    teams = await client.list_teams()
    await client.aclose()

    assert [t["id"] for t in teams] == [1, 2, 3]


async def test_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"data": [{"id": 1}], "meta": {"next_cursor": None}})

    client = _client(httpx.MockTransport(handler))
    teams = await client.list_teams()
    await client.aclose()

    assert calls["n"] == 2
    assert [t["id"] for t in teams] == [1]


async def test_iter_games_passes_filters_and_paginates() -> None:
    seen_params: list[dict[str, str]] = []
    pages = {
        None: {"data": [{"id": 10}], "meta": {"next_cursor": 5}},
        "5": {"data": [{"id": 11}], "meta": {"next_cursor": None}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.append(dict(request.url.params))
        return httpx.Response(200, json=pages[request.url.params.get("cursor")])

    client = _client(httpx.MockTransport(handler))
    games = [g async for g in client.iter_games(seasons=[2023], start_date="2024-01-01")]
    await client.aclose()

    assert [g["id"] for g in games] == [10, 11]
    assert seen_params[0]["seasons[]"] == "2023"
    assert seen_params[0]["start_date"] == "2024-01-01"


async def test_non_retryable_4xx_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = _client(httpx.MockTransport(handler))
    try:
        raised = False
        try:
            await client.list_teams()
        except httpx.HTTPStatusError as exc:
            raised = True
            assert exc.response.status_code == 401
        assert raised
    finally:
        await client.aclose()
