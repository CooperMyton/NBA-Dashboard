"""Integration tests for /teams and /players."""

import httpx


async def _bos_id(client: httpx.AsyncClient) -> int:
    teams = (await client.get("/api/v1/teams")).json()["data"]
    return next(t["id"] for t in teams if t["abbreviation"] == "BOS")


async def test_list_teams_returns_paged_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/teams")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"] == {"total": 2, "limit": 25, "offset": 0, "has_more": False}
    assert {t["abbreviation"] for t in body["data"]} == {"BOS", "LAL"}


async def test_list_teams_pagination_sets_has_more(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/teams", params={"limit": 1})).json()
    assert len(body["data"]) == 1
    assert body["meta"]["total"] == 2
    assert body["meta"]["has_more"] is True


async def test_list_teams_filters_by_conference(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/teams", params={"conference": "East"})).json()
    assert [t["abbreviation"] for t in body["data"]] == ["BOS"]


async def test_get_team_and_404(client: httpx.AsyncClient) -> None:
    team_id = await _bos_id(client)
    ok = await client.get(f"/api/v1/teams/{team_id}")
    assert ok.status_code == 200
    assert ok.json()["data"]["abbreviation"] == "BOS"

    missing = await client.get("/api/v1/teams/99999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


async def test_list_players_filter_and_search(client: httpx.AsyncClient) -> None:
    all_players = (await client.get("/api/v1/players")).json()
    assert all_players["meta"]["total"] == 2

    search = (await client.get("/api/v1/players", params={"search": "tatum"})).json()
    assert [p["last_name"] for p in search["data"]] == ["Tatum"]

    bos_id = await _bos_id(client)
    by_team = (await client.get("/api/v1/players", params={"team_id": bos_id})).json()
    assert [p["last_name"] for p in by_team["data"]] == ["Tatum"]


async def test_get_player_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/players/99999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
