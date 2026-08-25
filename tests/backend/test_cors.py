"""CORS is enabled for the configured frontend origin (needed for split-origin cloud deploys)."""

import httpx


async def test_cors_header_present_for_configured_origin(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
