"""Tests for the sync_players job: team mapping, free agents, and idempotency."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.player import Player
from backend.app.models.team import Team
from etl.jobs import sync_players, sync_teams
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


async def test_sync_players_does_not_clobber_roster_sync_fields(session: AsyncSession) -> None:
    """Regression test for the invariant that lets sync_rosters and sync_players coexist.

    sync_rosters (nba_api-backed, local-only) is the sole writer of ``roster_season`` and
    ``nba_player_id``. sync_players (balldontlie-backed) runs nightly and upserts the same
    players by ``external_id``. Its ``UPDATE_COLS`` deliberately excludes both fields; if a
    future edit ever added them back, the nightly sync would silently wipe every player's
    current-roster flag and NBA id.
    """
    await _seed_teams(session)
    players = load_fixture("players.json")

    # Seed Tatum (external_id=501) as if sync_rosters had already run against him.
    await sync_players.run(FakeClient(players=players), session)  # type: ignore[arg-type]
    tatum = (await session.execute(select(Player).where(Player.external_id == 501))).scalar_one()
    tatum.roster_season = 2026
    tatum.nba_player_id = 1628369
    await session.commit()

    # A nightly sync_players run over a payload containing the same player must not touch either
    # field, even though the provider payload has no notion of them.
    await sync_players.run(FakeClient(players=players), session)  # type: ignore[arg-type]

    await session.refresh(tatum)
    assert tatum.roster_season == 2026
    assert tatum.nba_player_id == 1628369


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
