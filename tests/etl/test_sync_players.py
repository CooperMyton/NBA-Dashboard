"""Tests for the sync_players job: team mapping, free agents, and idempotency."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.player import Player
from backend.app.models.team import Team
from etl.jobs import sync_players, sync_teams
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


async def test_skips_empty_name_players(session: AsyncSession) -> None:
    await sync_teams.run(FakeClient(teams=load_fixture("teams.json")), session)  # type: ignore[arg-type]
    players = [
        {"id": 1, "first_name": "Jayson", "last_name": "Tatum", "team": {"id": 1}},
        {"id": 2, "first_name": "", "last_name": "", "team": {"id": 1}},  # placeholder
    ]
    summary = await sync_players.run(FakeClient(players=players), session)  # type: ignore[arg-type]
    assert summary.rows_processed == 1
    assert summary.rows_rejected == 1


async def _player_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Player))).scalar_one()


async def _seed_teams(session: AsyncSession) -> None:
    await sync_teams.run(FakeClient(teams=load_fixture("teams.json")), session)  # type: ignore[arg-type]


async def test_loads_players_maps_team_and_is_idempotent(session: AsyncSession) -> None:
    await _seed_teams(session)
    players = load_fixture("players.json")

    first = await sync_players.run(FakeClient(players=players), session)  # type: ignore[arg-type]
    assert first.rows_processed == len(players)
    assert first.errors == []
    assert await _player_count(session) == len(players)

    # Tatum's provider team id 1 mapped to BOS surrogate id.
    bos_id = (await session.execute(select(Team.id).where(Team.abbreviation == "BOS"))).scalar_one()
    tatum = (await session.execute(select(Player).where(Player.external_id == 501))).scalar_one()
    assert tatum.team_id == bos_id

    await sync_players.run(FakeClient(players=players), session)  # type: ignore[arg-type]
    assert await _player_count(session) == len(players)


async def test_free_agent_has_null_team(session: AsyncSession) -> None:
    await _seed_teams(session)
    await sync_players.run(FakeClient(players=load_fixture("players.json")), session)  # type: ignore[arg-type]

    free_agent = (
        await session.execute(select(Player).where(Player.external_id == 503))
    ).scalar_one()
    assert free_agent.team_id is None


async def test_rejects_invalid_player(session: AsyncSession) -> None:
    await _seed_teams(session)
    players = [
        load_fixture("players.json")[0],
        {"id": 999},  # missing first_name/last_name
    ]
    summary = await sync_players.run(FakeClient(players=players), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 1
    assert summary.rows_rejected == 1
