"""Tests for the roster sync job."""

import pytest
from sqlalchemy import select

from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.models.team import Team
from etl.jobs import sync_rosters
from etl.providers.nba_stats import RosterEntry, StatLine


def roster(nba_id: int, name: str, abbr: str, age: float = 22.0, exp: int = 2) -> RosterEntry:
    return RosterEntry(
        nba_player_id=nba_id,
        name=name,
        team_abbr=abbr,
        position="G",
        jersey="1",
        age=age,
        experience=exp,
    )


def stat(
    nba_id: int,
    name: str,
    abbr: str,
    season: int,
    *,
    minutes: float = 30.0,
    points: float = 15.0,
    usage: float = 0.22,
    fg3_pct: float = 0.35,
    fg3a: float = 5.0,
    gp: int = 70,
) -> StatLine:
    return StatLine(
        nba_player_id=nba_id,
        name=name,
        team_abbr=abbr,
        season=season,
        games_played=gp,
        minutes=minutes,
        points=points,
        rebounds=4.0,
        assists=3.0,
        fg3_pct=fg3_pct,
        fg3a=fg3a,
        ts_pct=0.56,
        usage_pct=usage,
    )


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
    player = Player(external_id=900, first_name="Luka", last_name="Doncic", team_id=team.id)
    session.add(player)
    await session.commit()
    return team, player


async def test_run_marks_matched_players_as_rostered(session, seeded):
    team, player = seeded
    summary = await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(1, "Luka Doncic", "LAL")],
        stat_lines=[stat(1, "Luka Doncic", "LAL", 2025)],
    )
    await session.refresh(player)
    assert player.roster_season == 2026
    assert player.nba_player_id == 1
    assert summary.rows_processed == 1


async def test_run_inserts_unmatched_roster_players(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(2, "Yang Hansen", "LAL")],
        stat_lines=[],
    )
    rows = (await session.execute(select(Player).where(Player.nba_player_id == 2))).scalars().all()
    assert len(rows) == 1
    assert rows[0].first_name == "Yang"
    assert rows[0].last_name == "Hansen"
    assert rows[0].roster_season == 2026


async def test_run_clears_roster_season_for_players_no_longer_rostered(session, seeded):
    team, player = seeded
    player.roster_season = 2026
    await session.commit()

    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(3, "Someone Else", "LAL")],
        stat_lines=[],
    )
    await session.refresh(player)
    assert player.roster_season is None


async def test_run_stores_season_stats(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2024, 2025],
        rosters=[roster(1, "Luka Doncic", "LAL")],
        stat_lines=[stat(1, "Luka Doncic", "LAL", 2024), stat(1, "Luka Doncic", "LAL", 2025)],
    )
    rows = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert {row.season for row in rows} == {2024, 2025}


async def test_run_writes_breakout_insight(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2024, 2025],
        rosters=[roster(1, "Luka Doncic", "LAL", age=22.0, exp=2)],
        stat_lines=[
            stat(1, "Luka Doncic", "LAL", 2024, minutes=18.0, points=6.0, usage=0.16),
            stat(1, "Luka Doncic", "LAL", 2025, minutes=28.0, points=15.0, usage=0.23),
        ],
    )
    rows = (await session.execute(select(PlayerInsight))).scalars().all()
    assert [row.kind for row in rows] == ["breakout"]
    assert rows[0].detail


async def test_run_is_idempotent(session, seeded):
    args = {
        "roster_season": 2026,
        "stat_seasons": [2025],
        "rosters": [roster(1, "Luka Doncic", "LAL")],
        "stat_lines": [stat(1, "Luka Doncic", "LAL", 2025)],
    }
    await sync_rosters.run(session, **args)
    await sync_rosters.run(session, **args)
    stats = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert len(stats) == 1


async def test_run_ignores_stats_for_unrostered_players(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[],
        stat_lines=[stat(99, "Nobody Here", "LAL", 2025)],
    )
    stats = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert stats == []


async def test_run_dedupes_two_stints_in_same_season_keeping_most_games(session, seeded):
    """A traded player has two rows for one season; keep only the one with more games played."""
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(1, "Luka Doncic", "LAL")],
        stat_lines=[
            stat(1, "Luka Doncic", "DAL", 2025, gp=20, points=10.0, minutes=25.0),
            stat(1, "Luka Doncic", "LAL", 2025, gp=50, points=20.0, minutes=35.0),
        ],
    )
    rows = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert len(rows) == 1
    assert rows[0].season == 2025
    assert rows[0].games_played == 50
    assert rows[0].points == 20.0
