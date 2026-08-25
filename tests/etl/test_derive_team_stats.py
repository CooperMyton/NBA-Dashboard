"""Tests for the derive_team_stats job."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.team import Team
from backend.app.models.team_stat import TeamStat
from etl.jobs import derive_team_stats, sync_games, sync_teams
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


async def _seed_games(session: AsyncSession) -> None:
    await sync_teams.run(FakeClient(teams=load_fixture("teams.json")), session)  # type: ignore[arg-type]
    await sync_games.run(FakeClient(games=load_fixture("games.json")), session)  # type: ignore[arg-type]


async def _team_id(session: AsyncSession, abbreviation: str) -> int:
    return (
        await session.execute(select(Team.id).where(Team.abbreviation == abbreviation))
    ).scalar_one()


async def test_derives_two_rows_per_completed_game_and_is_idempotent(
    session: AsyncSession,
) -> None:
    await _seed_games(session)

    summary = await derive_team_stats.run(session)
    assert summary.rows_processed == 4  # 2 games x 2 sides
    assert summary.errors == []

    total = (await session.execute(select(func.count()).select_from(TeamStat))).scalar_one()
    assert total == 4

    # Boston won both games in the fixture.
    bos_id = await _team_id(session, "BOS")
    bos_rows = (
        (await session.execute(select(TeamStat).where(TeamStat.team_id == bos_id))).scalars().all()
    )
    assert len(bos_rows) == 2
    assert all(row.won for row in bos_rows)

    # Re-running recomputes the same rows, not duplicates.
    await derive_team_stats.run(session)
    total_again = (await session.execute(select(func.count()).select_from(TeamStat))).scalar_one()
    assert total_again == 4


async def test_no_completed_games_flags_data_quality_error(session: AsyncSession) -> None:
    await sync_teams.run(FakeClient(teams=load_fixture("teams.json")), session)  # type: ignore[arg-type]
    summary = await derive_team_stats.run(session)

    assert summary.rows_processed == 0
    assert summary.errors == ["no completed games to derive team stats from"]


async def test_points_for_and_against_are_oriented_per_team(session: AsyncSession) -> None:
    await _seed_games(session)
    await derive_team_stats.run(session)

    bos_id = await _team_id(session, "BOS")
    # Game 1001: BOS home 110, LAL 104 -> BOS points_for 110, against 104, home.
    home_row = (
        await session.execute(
            select(TeamStat).where(TeamStat.team_id == bos_id, TeamStat.is_home.is_(True))
        )
    ).scalar_one()
    assert home_row.points_for == 110
    assert home_row.points_against == 104
    assert home_row.won is True
