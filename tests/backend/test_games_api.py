"""Integration tests for /games."""

import httpx


async def test_list_games_and_filters(client: httpx.AsyncClient) -> None:
    all_games = (await client.get("/api/v1/games")).json()
    assert all_games["meta"]["total"] == 1
    game = all_games["data"][0]
    assert game["season"] == 2023
    assert game["status"] == "Final"
    assert game["home_team_score"] == 110

    assert (await client.get("/api/v1/games", params={"season": 2023})).json()["meta"]["total"] == 1
    assert (await client.get("/api/v1/games", params={"season": 2024})).json()["meta"]["total"] == 0
    assert (await client.get("/api/v1/games", params={"status": "Final"})).json()["meta"][
        "total"
    ] == 1
    assert (await client.get("/api/v1/games", params={"team_id": game["home_team_id"]})).json()[
        "meta"
    ]["total"] == 1


async def test_get_game_and_404(client: httpx.AsyncClient) -> None:
    game_id = (await client.get("/api/v1/games")).json()["data"][0]["id"]
    ok = await client.get(f"/api/v1/games/{game_id}")
    assert ok.status_code == 200
    assert ok.json()["data"]["id"] == game_id

    missing = await client.get("/api/v1/games/99999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


async def test_invalid_order_param_is_422(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/games", params={"order": "sideways"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
