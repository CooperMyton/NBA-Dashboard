"""Grade predictions against actual results once their games are final (docs/decisions.md D-008).

Fills ``actual_home_win`` / ``is_correct`` / ``settled_at`` for predictions whose game has a final
score and is not yet settled. Idempotent: settled rows are excluded on the next run.

Run as: ``python -m etl.jobs.settle_predictions``
"""

import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.model_prediction import ModelPrediction
from etl.core.summary import JobSummary

logger = get_logger("etl.settle_predictions")


async def run(session: AsyncSession, *, now: datetime | None = None) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="settle_predictions")
    stamp = now or datetime.now(UTC)

    stmt = (
        select(ModelPrediction, Game)
        .join(Game, ModelPrediction.game_id == Game.id)
        .where(
            Game.home_team_score.is_not(None),
            Game.visitor_team_score.is_not(None),
            func.lower(Game.status) == "final",
            ModelPrediction.settled_at.is_(None),
        )
    )

    settled = 0
    for prediction, game in (await session.execute(stmt)).tuples().all():
        home_score, away_score = game.home_team_score, game.visitor_team_score
        if home_score is None or away_score is None:
            continue  # unreachable given the filter; narrows Optional
        actual_home_win = home_score > away_score
        prediction.actual_home_win = actual_home_win
        prediction.is_correct = prediction.predicted_home_win == actual_home_win
        prediction.settled_at = stamp
        settled += 1

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    summary.rows_processed = settled
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
