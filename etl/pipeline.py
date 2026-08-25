"""Nightly ETL orchestration: sync → derive → invalidate cache.

Runs the jobs in dependency order in one session (each commits before the next reads), then
invalidates the affected Redis cache families. This is the single entrypoint the scheduler
calls (GitHub Actions nightly workflow / local cron).

Run as: ``python -m etl.pipeline``  (season defaults to the current NBA season;
override with the ``ETL_SEASONS`` env var, e.g. ``ETL_SEASONS=2023,2024``).
"""

import asyncio
from collections.abc import Sequence

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.cache import (
    PREDICTIONS_PREFIX,
    STANDINGS_PREFIX,
    TEAMS_PREFIX,
    invalidate_prefixes,
)
from backend.app.core.logging import get_logger
from etl.client.balldontlie import BalldontlieClient
from etl.core.summary import JobSummary
from etl.jobs import (
    derive_standings,
    derive_team_stats,
    predict_upcoming,
    settle_predictions,
    sync_games,
    sync_players,
    sync_teams,
)
from ml.pipeline.inference import Predictor

logger = get_logger("etl.pipeline")


async def run_pipeline(
    client: BalldontlieClient,
    session: AsyncSession,
    redis: Redis,
    *,
    seasons: Sequence[int] | None = None,
    predictor: Predictor | None = None,
) -> list[JobSummary]:
    season_list = list(seasons) if seasons else None
    # Order matters: load the dashboard-critical data (teams → games → derived standings) and
    # commit it before the high-volume players sync, so the dashboard populates even if the
    # (slow, rate-limited) players roster sync lags. Players is non-critical for the dashboard.
    summaries = [
        await sync_teams.run(client, session),
        await sync_games.run(client, session, seasons=season_list),
        await derive_team_stats.run(session),
        await derive_standings.run(session),
        await settle_predictions.run(session),
        await predict_upcoming.run(session, predictor, seasons=season_list),
        await sync_players.run(client, session),
    ]
    invalidated = await invalidate_prefixes(
        redis, [TEAMS_PREFIX, STANDINGS_PREFIX, PREDICTIONS_PREFIX]
    )
    logger.info(
        "etl.pipeline.complete",
        jobs=[s.job for s in summaries],
        rows={s.job: s.rows_processed for s in summaries},
        cache_keys_invalidated=invalidated,
        failed=any(s.errors for s in summaries),
    )
    return summaries


async def _main() -> int:
    import os
    from datetime import UTC, datetime

    from backend.app.core.config import get_settings
    from backend.app.core.logging import configure_logging
    from backend.app.core.redis import get_redis
    from backend.app.db.session import SessionLocal
    from etl.client.rate_limiter import make_provider_limiter
    from etl.core.season import current_nba_season
    from ml.pipeline.inference import load_active_predictor

    configure_logging()
    settings = get_settings()
    predictor = load_active_predictor()

    seasons_env = os.environ.get("ETL_SEASONS")
    if seasons_env:
        seasons = [int(part.strip()) for part in seasons_env.split(",") if part.strip()]
    else:
        seasons = [current_nba_season(datetime.now(UTC).date())]

    limiter = make_provider_limiter(settings.provider_rate_limit_per_min)
    redis = get_redis()
    try:
        async with (
            BalldontlieClient(
                settings.balldontlie_api_key, settings.balldontlie_base_url, limiter
            ) as client,
            SessionLocal() as session,
        ):
            summaries = await run_pipeline(
                client, session, redis, seasons=seasons, predictor=predictor
            )
    finally:
        await redis.aclose()

    return 1 if any(s.errors for s in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
