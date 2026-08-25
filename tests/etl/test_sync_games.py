"""Tests for the sync_games job: team mapping, idempotency, and referential guards."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.game import Game
from etl.jobs import sync_games, sync_teams
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


async def _game_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Game))).scalar_one()


async def _seed_teams(session: AsyncSession) -> None:
    await sync_teams.run(FakeClient(teams=load_fixture("teams.json")), session)  # type: ignore[arg-type]


async def test_loads_games_and_is_idempotent(session: AsyncSession) -> None:
    await _seed_teams(session)
    games = load_fixture("games.json")

    first = await sync_games.run(FakeClient(games=games), session)  # type: ignore[arg-type]
    assert first.rows_processed == len(games)
    assert first.rows_rejected == 0
    assert first.errors == []
    assert await _game_count(session) == len(games)

    await sync_games.run(FakeClient(games=games), session)  # type: ignore[arg-type]
    assert await _game_count(session) == len(games)


async def test_maps_provider_team_ids_and_parses_fields(session: AsyncSession) -> None:
    await _seed_teams(session)
    await sync_games.run(FakeClient(games=load_fixture("games.json")), session)  # type: ignore[arg-type]

    game = (await session.execute(select(Game).where(Game.external_id == 1001))).scalar_one()
    # Provider team ids 1 and 2 mapped to our surrogate ids (both present, distinct).
    assert game.home_team_id is not None
    assert game.visitor_team_id is not None
    assert game.home_team_id != game.visitor_team_id
    assert game.game_date == date(2024, 1, 15)
    assert game.season == 2023


async def test_rejects_games_with_unknown_teams(session: AsyncSession) -> None:
    # Teams not seeded -> every game references an unknown team and is rejected.
    games = load_fixture("games.json")
    summary = await sync_games.run(FakeClient(games=games), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 0
    assert summary.rows_rejected == len(games)
    assert await _game_count(session) == 0


async def test_empty_load_flags_data_quality_error(session: AsyncSession) -> None:
    await _seed_teams(session)
    summary = await sync_games.run(FakeClient(games=[]), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 0
    assert summary.errors == ["no games loaded"]


async def test_identical_home_and_away_flags_data_quality_error(session: AsyncSession) -> None:
    await _seed_teams(session)
    bad = load_fixture("games.json")[0]
    bad["visitor_team"] = {"id": bad["home_team"]["id"]}  # same team on both sides
    summary = await sync_games.run(FakeClient(games=[bad]), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 1
    assert any("identical home/away" in e for e in summary.errors)
