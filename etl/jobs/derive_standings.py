"""Derive per-season standings from team_stats (docs/decisions.md D-004).

Aggregates wins/losses, win %, home/road records, current streak, and conference rank.
The aggregation is a pure function (``compute_standings``) so it is unit-testable without a DB.
Idempotent via upsert on ``(season, team_id)``.

Run as: ``python -m etl.jobs.derive_standings``
"""

import asyncio
import time
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.standing import Standing
from backend.app.models.team import Team
from backend.app.models.team_stat import TeamStat
from etl.core.summary import JobSummary
from etl.core.upsert import upsert

logger = get_logger("etl.derive_standings")

UPDATE_COLS = [
    "wins",
    "losses",
    "win_pct",
    "conference",
    "conference_rank",
    "home_record",
    "road_record",
    "streak",
]

# One completed game from a team's perspective: (game_date, won, is_home).
TeamGame = tuple[date, bool, bool]
# A row from the team_stats/games join: (season, team_id, won, is_home, game_date).
StandingRecord = tuple[int, int, bool, bool, date]


def _streak(results: list[bool]) -> str | None:
    """Current streak from an oldest→newest list of results, e.g. ``"W3"`` / ``"L2"``."""
    if not results:
        return None
    last = results[-1]
    count = 0
    for result in reversed(results):
        if result != last:
            break
        count += 1
    return f"{'W' if last else 'L'}{count}"


def _assign_conference_ranks(standings: list[dict[str, Any]]) -> None:
    by_conference: dict[tuple[int, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in standings:
        by_conference[(row["season"], row["conference"])].append(row)
    for group in by_conference.values():
        group.sort(key=lambda row: row["win_pct"], reverse=True)
        for rank, row in enumerate(group, start=1):
            row["conference_rank"] = rank


def compute_standings(
    records: list[StandingRecord], conference_by_team: dict[int, str]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[TeamGame]] = defaultdict(list)
    for season, team_id, won, is_home, game_date in records:
        grouped[(season, team_id)].append((game_date, won, is_home))

    standings: list[dict[str, Any]] = []
    for (season, team_id), games in grouped.items():
        games.sort(key=lambda g: g[0])
        results = [won for _, won, _ in games]
        wins = sum(results)
        losses = len(results) - wins
        played = wins + losses
        home_wins = sum(1 for _, won, is_home in games if is_home and won)
        home_losses = sum(1 for _, won, is_home in games if is_home and not won)
        road_wins = sum(1 for _, won, is_home in games if not is_home and won)
        road_losses = sum(1 for _, won, is_home in games if not is_home and not won)
        standings.append(
            {
                "season": season,
                "team_id": team_id,
                "wins": wins,
                "losses": losses,
                "win_pct": round(wins / played, 4) if played else 0.0,
                "conference": conference_by_team.get(team_id),
                "conference_rank": None,
                "home_record": f"{home_wins}-{home_losses}",
                "road_record": f"{road_wins}-{road_losses}",
                "streak": _streak(results),
            }
        )

    _assign_conference_ranks(standings)
    return standings


async def run(session: AsyncSession, *, season: int | None = None) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="derive_standings")

    # Standings are regular season only — exclude playoff games (postseason=True).
    stmt = (
        select(TeamStat.season, TeamStat.team_id, TeamStat.won, TeamStat.is_home, Game.game_date)
        .join(Game, TeamStat.game_id == Game.id)
        .where(Game.postseason.is_(False))
    )
    if season is not None:
        stmt = stmt.where(TeamStat.season == season)
    records = list((await session.execute(stmt)).tuples().all())
    conference_by_team = dict(
        (await session.execute(select(Team.id, Team.conference))).tuples().all()
    )

    rows = compute_standings(records, conference_by_team)

    try:
        summary.rows_processed = await upsert(
            session, Standing, rows, ["season", "team_id"], UPDATE_COLS
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    if not rows:
        summary.errors.append("no team stats to derive standings from")
    summary.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("etl.job.summary", **summary.as_dict())
    return summary


async def _main() -> int:
    from backend.app.core.logging import configure_logging
    from backend.app.db.session import SessionLocal

    configure_logging()
    async with SessionLocal() as session:
        summary = await run(session)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
