"""Tests for the model registry endpoint."""

import httpx


async def test_model_registry_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/model/registry")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "active" in data
    assert isinstance(data["versions"], list)


async def test_predict_requires_api_key(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/model/predict",
        json={"home_team_id": 1, "visitor_team_id": 2, "season": 2024},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
