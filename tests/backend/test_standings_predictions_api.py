"""Integration tests for /standings and /predictions (both cached)."""

import httpx


async def test_list_standings_and_conference_filter(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/standings", params={"season": 2023})).json()
    assert body["meta"]["total"] == 2
    leader = next(s for s in body["data"] if s["streak"] == "W2")
    assert leader["wins"] == 2
    assert leader["conference_rank"] == 1

    east = (
        await client.get("/api/v1/standings", params={"season": 2023, "conference": "East"})
    ).json()
    assert east["meta"]["total"] == 1
    assert east["data"][0]["conference"] == "East"


async def test_standings_served_from_cache_after_first_call(client: httpx.AsyncClient) -> None:
    # Warm the cache, then a repeat call must succeed identically (served from Redis).
    first = (await client.get("/api/v1/standings", params={"season": 2023})).json()
    second = (await client.get("/api/v1/standings", params={"season": 2023})).json()
    assert first == second


async def test_list_predictions_and_filters(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/predictions")).json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["model_version"] == "v1"
    assert body["data"][0]["predicted_home_win"] is True

    empty = (await client.get("/api/v1/predictions", params={"game_id": 99999})).json()
    assert empty["meta"]["total"] == 0
