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
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.api.deps import Pagination
from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.models.team import Team
from backend.app.services import players as players_service
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


@pytest.fixture
async def seeded_with_stats(session, seeded):
    active, retired = seeded
    session.add_all(
        [
            PlayerSeasonStat(
                player_id=active.id,
                season=2024,
                team_id=active.team_id,
                games_played=60,
                minutes=30.0,
                points=20.0,
                rebounds=5.0,
                assists=4.0,
                fg3_pct=0.35,
                fg3a=5.0,
                ts_pct=0.55,
                usage_pct=0.25,
            ),
            PlayerSeasonStat(
                player_id=active.id,
                season=2025,
                team_id=active.team_id,
                games_played=70,
                minutes=34.5,
                points=28.6,
                rebounds=8.2,
                assists=8.8,
                fg3_pct=0.38,
                fg3a=7.0,
                ts_pct=0.588,
                usage_pct=0.31,
            ),
        ]
    )
    await session.commit()
    return active, retired


async def test_get_player_returns_highest_season_stats(client, seeded_with_stats):
    active, _ = seeded_with_stats
    response = await client.get(f"/api/v1/players/{active.id}")
    assert response.status_code == 200
    stats = response.json()["data"]["latest_stats"]
    assert stats is not None
    assert stats["season"] == 2025
    assert stats["games_played"] == 70
    assert stats["minutes"] == 34.5
    assert stats["points"] == 28.6
    assert stats["rebounds"] == 8.2
    assert stats["assists"] == 8.8
    assert stats["ts_pct"] == 0.588
    assert stats["usage_pct"] == 0.31


async def test_get_player_without_stats_returns_null(client, seeded):
    _, retired = seeded
    response = await client.get(f"/api/v1/players/{retired.id}")
    assert response.status_code == 200
    assert response.json()["data"]["latest_stats"] is None


async def test_list_players_attaches_correct_stats_per_player(client, seeded_with_stats):
    response = await client.get("/api/v1/players")
    assert response.status_code == 200
    rows = {row["last_name"]: row for row in response.json()["data"]}
    assert rows["Doncic"]["latest_stats"]["season"] == 2025
    assert rows["Doncic"]["latest_stats"]["points"] == 28.6
    assert rows["Abdul-Jabbar"]["latest_stats"] is None


async def test_list_players_fetches_stats_in_a_single_query(session, seeded_with_stats):
    """Guards against N+1: one page of players must issue exactly one stats query, not one
    per player, regardless of how many players are on the page."""
    queries: list[str] = []
    engine = session.bind.sync_engine

    def _record(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        await players_service.list_players(session, page=Pagination(limit=25, offset=0))
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    stat_queries = [q for q in queries if "player_season_stats" in q]
    assert len(stat_queries) == 1
