"""Backtest the active model over completed games and record settled predictions.

For each completed game (chronologically), predict using ONLY prior games as features (leak-free),
then settle immediately against the known result. This populates model_predictions with realistic
historical accuracy/calibration for the Model Lab and Prediction Tracker pages.

Idempotent via upsert on ``(game_id, model_version)``.

Run as: ``python -m etl.jobs.backtest_predictions`` (backtests the current NBA season by default).
"""

import asyncio
import time
from datetime import UTC, datetime
from datetime import time as dtime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.model_prediction import ModelPrediction
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from ml.pipeline.collect import collect_games
from ml.pipeline.features import FeatureBuilder
from ml.pipeline.inference import Predictor

logger = get_logger("etl.backtest_predictions")

UPDATE_COLS = [
    "predicted_home_win_prob",
    "predicted_home_win",
    "actual_home_win",
    "is_correct",
    "predicted_at",
    "settled_at",
]


async def run(
    session: AsyncSession,
    predictor: Predictor | None,
    *,
    seasons: list[int],
) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="backtest_predictions")

    if predictor is None:
        logger.info("etl.backtest.no_active_model")
        summary.duration_ms = int((time.monotonic() - started) * 1000)
        return summary

    # One builder over all seasons chronologically, so Elo carries across seasons exactly as it
    # does during training (features_for is called before observe → leak-free).
    games = await collect_games(session, seasons=seasons)
    builder = FeatureBuilder()
    rows: list[dict[str, Any]] = []
    for game in games:
        features = builder.features_for(
            game.season, game.game_date, game.home_team_id, game.visitor_team_id
        )
        probability = predictor.predict_proba([features])[0]
        predicted_home_win = probability >= 0.5
        actual_home_win = game.home_score > game.visitor_score
        # Stamp with the game date so the tracker's time axis spans the season.
        stamp = datetime.combine(game.game_date, dtime.min, tzinfo=UTC)
        rows.append(
            {
                "game_id": game.game_id,
                "model_version": predictor.model_version,
                "predicted_home_win_prob": probability,
                "predicted_home_win": predicted_home_win,
                "actual_home_win": actual_home_win,
                "is_correct": predicted_home_win == actual_home_win,
                "predicted_at": stamp,
                "settled_at": stamp,
            }
        )
        builder.observe(game)

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
    from etl.core.season import current_nba_season
    from ml.pipeline.inference import load_active_predictor

    configure_logging()
    predictor = load_active_predictor()
    season = current_nba_season(datetime.now(UTC).date())
    async with SessionLocal() as session:
        summary = await run(session, predictor, seasons=[season])
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
