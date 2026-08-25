"""Derive per-team, per-game stat lines from completed games (docs/decisions.md D-005).

For every completed game (final, both scores present) this writes two ``team_stats`` rows —
one per side — with points for/against and the win flag. Idempotent via upsert on
``(game_id, team_id)``.

Run as: ``python -m etl.jobs.derive_team_stats``
"""

import asyncio
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.team_stat import TeamStat
from etl.core.summary import JobSummary
from etl.core.upsert import upsert

logger = get_logger("etl.derive_team_stats")

UPDATE_COLS = ["season", "is_home", "points_for", "points_against", "won"]


def _rows_for_game(game: Game) -> list[dict[str, Any]]:
    home_score = game.home_team_score
    away_score = game.visitor_team_score
    assert home_score is not None and away_score is not None  # guaranteed by the query filter
    return [
        {
            "game_id": game.id,
            "team_id": game.home_team_id,
            "season": game.season,
            "is_home": True,
            "points_for": home_score,
            "points_against": away_score,
            "won": home_score > away_score,
        },
        {
            "game_id": game.id,
            "team_id": game.visitor_team_id,
            "season": game.season,
            "is_home": False,
            "points_for": away_score,
            "points_against": home_score,
            "won": away_score > home_score,
        },
    ]


async def run(session: AsyncSession, *, season: int | None = None) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="derive_team_stats")

    stmt = select(Game).where(
        Game.home_team_score.is_not(None),
        Game.visitor_team_score.is_not(None),
        func.lower(Game.status) == "final",
    )
    if season is not None:
        stmt = stmt.where(Game.season == season)
    games = (await session.execute(stmt)).scalars().all()

    rows: list[dict[str, Any]] = []
    for game in games:
        rows.extend(_rows_for_game(game))

    try:
        summary.rows_processed = await upsert(
            session, TeamStat, rows, ["game_id", "team_id"], UPDATE_COLS
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    if not rows:
        summary.errors.append("no completed games to derive team stats from")
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
