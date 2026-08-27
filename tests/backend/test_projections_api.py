"""Integration tests for /projections (cached)."""

import httpx


async def test_list_projections_for_a_season(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/projections", params={"season": 2026})).json()
    assert body["meta"]["total"] == 2

    first = body["data"][0]
    assert first["season"] == 2026
    assert first["model_version"] == "v1"
    assert 0.0 <= first["win_title_pct"] <= 100.0
    assert first["simulations"] == 100

    # Ordered strongest-first.
    wins = [row["proj_wins"] for row in body["data"]]
    assert wins == sorted(wins, reverse=True)


async def test_projections_empty_for_unknown_season(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/projections", params={"season": 1999})).json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


async def test_projections_served_from_cache_after_first_call(client: httpx.AsyncClient) -> None:
    first = (await client.get("/api/v1/projections", params={"season": 2026})).json()
    second = (await client.get("/api/v1/projections", params={"season": 2026})).json()
    assert first == second
