"""Sync players from the provider into the ``players`` table (idempotent).

Teams must be synced first; a player's team is resolved to our surrogate id (or left null for
free agents / unknown teams — players outlive team changes, so this is not a rejection).

Run as: ``python -m etl.jobs.sync_players``
"""

import asyncio
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.player import Player
from etl.client.balldontlie import BalldontlieClient
from etl.core.refs import load_team_map
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from etl.schemas.player import RawPlayer

logger = get_logger("etl.sync_players")

UPDATE_COLS = [
    "first_name",
    "last_name",
    "position",
    "height",
    "weight",
    "jersey_number",
    "college",
    "country",
    "team_id",
]


def _to_row(player: RawPlayer, team_id: int | None) -> dict[str, Any]:
    return {
        "external_id": player.id,
        "first_name": player.first_name,
        "last_name": player.last_name,
        "position": player.position,
        "height": player.height,
        "weight": player.weight,
        "jersey_number": player.jersey_number,
        "college": player.college,
        "country": player.country,
        "team_id": team_id,
    }


async def run(client: BalldontlieClient, session: AsyncSession) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="sync_players")
    team_map = await load_team_map(session)

    rows: list[dict[str, Any]] = []
    for raw in await client.list_players():
        try:
            player = RawPlayer.model_validate(raw)
        except ValidationError as exc:
            summary.rows_rejected += 1
            logger.warning("etl.row.rejected", job=summary.job, error=str(exc))
            continue
        # Skip placeholder/non-NBA entries the provider returns with no name.
        if not player.first_name.strip() and not player.last_name.strip():
            summary.rows_rejected += 1
            continue
        team_id = team_map.get(player.team.id) if player.team else None
        rows.append(_to_row(player, team_id))

    try:
        summary.rows_processed = await upsert(session, Player, rows, ["external_id"], UPDATE_COLS)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    if not rows:
        summary.errors.append("no players loaded")
    summary.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("etl.job.summary", **summary.as_dict())
    return summary


async def _main() -> int:
    from backend.app.core.config import get_settings
    from backend.app.core.logging import configure_logging
    from backend.app.db.session import SessionLocal
    from etl.client.rate_limiter import make_provider_limiter

    configure_logging()
    settings = get_settings()
    limiter = make_provider_limiter(settings.provider_rate_limit_per_min)
    async with (
        BalldontlieClient(
            settings.balldontlie_api_key, settings.balldontlie_base_url, limiter
        ) as client,
        SessionLocal() as session,
    ):
        summary = await run(client, session)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
