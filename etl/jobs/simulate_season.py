"""Simulate a season many times and store per-team projections.

Reads the active model only — never trains. Idempotent via upsert on
``(season, team_id, model_version)``, so re-running refreshes the projection. No-ops when no
model is active.

Run as: ``python -m etl.jobs.simulate_season``
"""

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.season_projection import SeasonProjection
from backend.app.models.team import Team
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from ml.pipeline.collect import collect_games
from ml.pipeline.features import FeatureBuilder
from ml.pipeline.inference import Predictor
from ml.pipeline.simulation import ScheduledGame, run_simulations

logger = get_logger("etl.simulate_season")

DEFAULT_SIMULATIONS = 2000

UPDATE_COLS = [
    "proj_wins",
    "proj_losses",
    "wins_p10",
    "wins_p50",
    "wins_p90",
    "make_playoffs_pct",
    "win_conference_pct",
    "win_title_pct",
    "avg_seed",
    "simulations",
    "generated_at",
]


async def run(
    session: AsyncSession,
    predictor: Predictor | None,
    *,
    season: int,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = 0,
    now: datetime | None = None,
) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="simulate_season")

    if predictor is None:
        logger.info("etl.simulate_season.no_active_model")
        summary.duration_ms = int((time.monotonic() - started) * 1000)
        return summary

    stamp = now or datetime.now(UTC)

    conferences = {
        team.id: team.conference for team in (await session.execute(select(Team))).scalars().all()
    }

    scheduled = (
        (
            await session.execute(
                select(Game)
                .where(Game.season == season)
                .where(func.lower(Game.status) != "final")
                .where(Game.postseason.is_(False))
                .order_by(Game.game_date, Game.id)
            )
        )
        .scalars()
        .all()
    )
    if not scheduled:
        logger.info("etl.simulate_season.no_schedule", season=season)
        summary.duration_ms = int((time.monotonic() - started) * 1000)
        return summary

    schedule = [
        ScheduledGame(
            game_id=g.id,
            season=g.season,
            game_date=g.game_date,
            home_team_id=g.home_team_id,
            visitor_team_id=g.visitor_team_id,
        )
        for g in scheduled
    ]

    builder = FeatureBuilder()
    for record in await collect_games(session):
        builder.observe(record)

    projections = run_simulations(
        builder, schedule, predictor, conferences, simulations=simulations, seed=seed
    )

    rows: list[dict[str, Any]] = [
        {
            "season": season,
            "team_id": p.team_id,
            "model_version": predictor.model_version,
            "proj_wins": p.proj_wins,
            "proj_losses": p.proj_losses,
            "wins_p10": p.wins_p10,
            "wins_p50": p.wins_p50,
            "wins_p90": p.wins_p90,
            "make_playoffs_pct": p.make_playoffs_pct,
            "win_conference_pct": p.win_conference_pct,
            "win_title_pct": p.win_title_pct,
            "avg_seed": p.avg_seed,
            "simulations": simulations,
            "generated_at": stamp,
        }
        for p in projections
    ]

    try:
        summary.rows_processed = await upsert(
            session,
            SeasonProjection,
            rows,
            ["season", "team_id", "model_version"],
            UPDATE_COLS,
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
    season = int(os.getenv("PROJECTION_SEASON", "2026"))
    simulations = int(os.getenv("PROJECTION_SIMULATIONS", str(DEFAULT_SIMULATIONS)))
    async with SessionLocal() as session:
        summary = await run(session, predictor, season=season, simulations=simulations)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
