"""Tests for the derive_standings job and its pure aggregation function."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.standing import Standing
from backend.app.models.team import Team
from etl.jobs import derive_standings, derive_team_stats, sync_games, sync_teams
from etl.jobs.derive_standings import _streak, compute_standings
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


def test_streak_reads_from_most_recent() -> None:
    assert _streak([True, True, True]) == "W3"
    assert _streak([False, True]) == "W1"
    assert _streak([True, False, False]) == "L2"
    assert _streak([]) is None


def test_compute_standings_ranks_by_win_pct() -> None:
    records = [
        (2023, 1, True, True, date(2024, 1, 1)),
        (2023, 1, True, False, date(2024, 1, 3)),
        (2023, 2, False, True, date(2024, 1, 2)),
    ]
    conference = {1: "East", 2: "East"}
    by_team = {row["team_id"]: row for row in compute_standings(records, conference)}

    assert by_team[1]["wins"] == 2
    assert by_team[1]["win_pct"] == 1.0
    assert by_team[1]["streak"] == "W2"
    assert by_team[1]["conference_rank"] == 1
    assert by_team[2]["conference_rank"] == 2
    assert by_team[2]["home_record"] == "0-1"


async def _seed_and_derive_stats(session: AsyncSession) -> None:
    await sync_teams.run(FakeClient(teams=load_fixture("teams.json")), session)  # type: ignore[arg-type]
    await sync_games.run(FakeClient(games=load_fixture("games.json")), session)  # type: ignore[arg-type]
    await derive_team_stats.run(session)


async def test_derives_standings_end_to_end(session: AsyncSession) -> None:
    await _seed_and_derive_stats(session)

    summary = await derive_standings.run(session)
    assert summary.rows_processed == 2
    assert summary.errors == []

    rows = (await session.execute(select(Standing, Team.abbreviation).join(Team))).all()
    by_abbr = {abbr: standing for standing, abbr in rows}

    bos = by_abbr["BOS"]
    assert (bos.wins, bos.losses) == (2, 0)
    assert bos.win_pct == 1.0
    assert bos.streak == "W2"
    assert bos.home_record == "1-0"
    assert bos.road_record == "1-0"
    assert bos.conference_rank == 1  # only East team

    lal = by_abbr["LAL"]
    assert (lal.wins, lal.losses) == (0, 2)
    assert lal.streak == "L2"


async def test_standings_exclude_playoff_games(session: AsyncSession) -> None:
    from datetime import date

    from backend.app.models.game import Game
    from backend.app.models.standing import Standing
    from backend.app.models.team import Team
    from etl.jobs import derive_team_stats

    bos = Team(
        external_id=1,
        abbreviation="BOS",
        name="Celtics",
        full_name="Boston Celtics",
        city="Boston",
        conference="East",
        division="Atlantic",
    )
    lal = Team(
        external_id=2,
        abbreviation="LAL",
        name="Lakers",
        full_name="Los Angeles Lakers",
        city="Los Angeles",
        conference="West",
        division="Pacific",
    )
    session.add_all([bos, lal])
    await session.flush()
    session.add_all(
        [
            Game(
                external_id=1,
                season=2023,
                game_date=date(2024, 1, 1),
                start_time=None,
                status="Final",
                postseason=False,
                period=4,
                home_team_id=bos.id,
                visitor_team_id=lal.id,
                home_team_score=110,
                visitor_team_score=100,
            ),
            Game(  # playoff game — must NOT count toward standings
                external_id=2,
                season=2023,
                game_date=date(2024, 5, 1),
                start_time=None,
                status="Final",
                postseason=True,
                period=4,
                home_team_id=bos.id,
                visitor_team_id=lal.id,
                home_team_score=115,
                visitor_team_score=90,
            ),
        ]
    )
    await session.commit()
    await derive_team_stats.run(session)

    await derive_standings.run(session)
    bos_standing = (
        await session.execute(select(Standing).where(Standing.team_id == bos.id))
    ).scalar_one()
    assert (bos_standing.wins, bos_standing.losses) == (1, 0)  # regular-season game only


async def test_no_team_stats_flags_data_quality_error(session: AsyncSession) -> None:
    summary = await derive_standings.run(session)

    assert summary.rows_processed == 0
    assert summary.errors == ["no team stats to derive standings from"]


async def test_derive_standings_is_idempotent(session: AsyncSession) -> None:
    await _seed_and_derive_stats(session)
    await derive_standings.run(session)
    await derive_standings.run(session)

    count = len((await session.execute(select(Standing))).scalars().all())
    assert count == 2
