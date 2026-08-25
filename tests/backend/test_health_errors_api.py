"""Integration tests for health probes and error shapes."""

import httpx


async def test_health_is_liveness_only(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"data": {"status": "ok"}}


async def test_ready_checks_db_and_redis(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["data"]["checks"] == {"database": True, "redis": True}


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_validation_error_uses_error_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/teams", params={"limit": 0})  # below ge=1
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
