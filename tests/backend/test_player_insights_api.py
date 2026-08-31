"""Tests for the player insights endpoint and the active filter.

Uses module-local `client`/`session` fixtures on a bare (unseeded) database, rather than the
shared `tests/backend/conftest.py` ones: those pre-seed two teams/players whose ``external_id``
and ``abbreviation`` values collide with the fixtures below, and whose presence would break the
``total`` assertions here, which assume nothing but what `seeded` inserts. The engine/session and
dependency-override plumbing itself is not duplicated: both fixtures below just call the shared
`build_test_db`/`build_test_client` factories from `conftest.py` with no seed.
"""

import pathlib
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.team import Team
from tests.backend.conftest import build_test_client, build_test_db


@pytest_asyncio.fixture
async def _db_maker(
    tmp_path: pathlib.Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async for maker in build_test_db(tmp_path):
        yield maker


@pytest_asyncio.fixture
async def session(
    _db_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with _db_maker() as db_session:
        yield db_session


@pytest_asyncio.fixture
async def client(
    _db_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[httpx.AsyncClient]:
    async for test_client in build_test_client(_db_maker):
        yield test_client


@pytest.fixture
async def seeded(session):
    team = Team(
        external_id=1,
        abbreviation="LAL",
        name="Lakers",
        full_name="Los Angeles Lakers",
        city="Los Angeles",
        conference="West",
        division="Pacific",
    )
    session.add(team)
    await session.flush()
    active = Player(
        external_id=1,
        first_name="Luka",
        last_name="Doncic",
        team_id=team.id,
        roster_season=2026,
    )
    retired = Player(external_id=2, first_name="Kareem", last_name="Abdul-Jabbar", team_id=team.id)
    session.add_all([active, retired])
    await session.flush()
    session.add(
        PlayerInsight(
            player_id=active.id,
            season=2025,
            kind="breakout",
            score=3.2,
            detail="18.0 to 28.0 minutes",
        )
    )
    await session.commit()
    return active, retired


async def test_players_active_filter_excludes_historical(client, seeded):
    response = await client.get("/api/v1/players?active=true")
    assert response.status_code == 200
    names = [row["last_name"] for row in response.json()["data"]]
    assert names == ["Doncic"]


async def test_players_without_filter_returns_everyone(client, seeded):
    response = await client.get("/api/v1/players")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 2


async def test_insights_route_is_not_shadowed_by_the_id_route(client, seeded):
    # Declared after /players/{player_id} this returns 422 as FastAPI tries to parse "insights".
    response = await client.get("/api/v1/players/insights?season=2025")
    assert response.status_code == 200


async def test_insights_returns_supporting_detail(client, seeded):
    response = await client.get("/api/v1/players/insights?season=2025")
    row = response.json()["data"][0]
    assert row["kind"] == "breakout"
    assert row["detail"] == "18.0 to 28.0 minutes"
    assert row["team_abbreviation"] == "LAL"
    assert row["last_name"] == "Doncic"


async def test_insights_filters_by_kind(client, seeded):
    response = await client.get("/api/v1/players/insights?season=2025&kind=regression")
    assert response.json()["data"] == []


async def test_insights_filters_by_season(client, seeded):
    response = await client.get("/api/v1/players/insights?season=2024")
    assert response.json()["data"] == []


async def test_get_player_by_id_still_works(client, seeded):
    active, _ = seeded
    response = await client.get(f"/api/v1/players/{active.id}")
    assert response.status_code == 200
    assert response.json()["data"]["last_name"] == "Doncic"
