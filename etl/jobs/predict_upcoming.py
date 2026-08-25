"""Run the active model over upcoming (unplayed) games and write model_predictions.

Reads the active model only — never trains. Idempotent via upsert on ``(game_id, model_version)``,
so re-running refreshes probabilities. If no model is active, the job no-ops (expected before the
first model is trained).

Run as: ``python -m etl.jobs.predict_upcoming``
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.model_prediction import ModelPrediction
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from ml.pipeline.collect import collect_games
from ml.pipeline.features import FeatureBuilder
from ml.pipeline.inference import Predictor

logger = get_logger("etl.predict_upcoming")

UPDATE_COLS = ["predicted_home_win_prob", "predicted_home_win", "predicted_at"]


async def run(
    session: AsyncSession,
    predictor: Predictor | None,
    *,
    seasons: list[int] | None = None,
    now: datetime | None = None,
) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="predict_upcoming")

    if predictor is None:
        logger.info("etl.predict_upcoming.no_active_model")
        summary.duration_ms = int((time.monotonic() - started) * 1000)
        return summary

    stamp = now or datetime.now(UTC)
    # Unplayed games: not yet Final (scheduled games carry their tip-off time as the status,
    # and providers may return 0-0 rather than null scores).
    stmt = select(Game).where(func.lower(Game.status) != "final")
    if seasons:
        stmt = stmt.where(Game.season.in_(seasons))
    games = (await session.execute(stmt.order_by(Game.game_date, Game.id))).scalars().all()

    # Build state from ALL completed games once, so upcoming games (even a brand-new season with
    # no results yet) get each team's carried-over Elo rather than a cold default.
    history = await collect_games(session)
    builder = FeatureBuilder()
    for record in history:
        builder.observe(record)

    rows: list[dict[str, Any]] = []
    for game in games:
        row_features = builder.features_for(
            game.season, game.game_date, game.home_team_id, game.visitor_team_id
        )
        probability = predictor.predict_proba([row_features])[0]
        rows.append(
            {
                "game_id": game.id,
                "model_version": predictor.model_version,
                "predicted_home_win_prob": probability,
                "predicted_home_win": probability >= 0.5,
                "predicted_at": stamp,
            }
        )

    try:
        summary.rows_processed = await upsert(
            session, ModelPrediction, rows, ["game_id", "model_version"], UPDATE_COLS
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    summary.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("etl.job.summary", **summary.as_dict())
    return summary


async def _main() -> int:
    from backend.app.core.logging import configure_logging
    from backend.app.db.session import SessionLocal
    from ml.pipeline.inference import load_active_predictor

    configure_logging()
    predictor = load_active_predictor()
    async with SessionLocal() as session:
        summary = await run(session, predictor)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
