"""Sync games from the provider into the ``games`` table (idempotent).

Games reference our surrogate team ids, so teams must be synced first; a game referencing an
unknown team is rejected and logged (referential-integrity guard).

Run as: ``python -m etl.jobs.sync_games`` (defaults to the current/most recent season window).
"""

import asyncio
import time
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from etl.client.balldontlie import BalldontlieClient
from etl.core.refs import load_team_map
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from etl.schemas.game import RawGame

logger = get_logger("etl.sync_games")

UPDATE_COLS = [
    "season",
    "game_date",
    "start_time",
    "status",
    "postseason",
    "period",
    "home_team_id",
    "visitor_team_id",
    "home_team_score",
    "visitor_team_score",
]


def _parse_date(value: str) -> date:
    # Accepts "YYYY-MM-DD" or a full ISO datetime; the date portion is the first 10 chars.
    return date.fromisoformat(value[:10])


def _parse_start_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_row(game: RawGame, home_team_id: int, visitor_team_id: int) -> dict[str, Any]:
    return {
        "external_id": game.id,
        "season": game.season,
        "game_date": _parse_date(game.date),
        "start_time": _parse_start_time(game.start_datetime),
        "status": game.status,
        "postseason": game.postseason,
        "period": game.period,
        "home_team_id": home_team_id,
        "visitor_team_id": visitor_team_id,
        "home_team_score": game.home_team_score,
        "visitor_team_score": game.visitor_team_score,
    }


def _quality_checks(rows: list[dict[str, Any]], summary: JobSummary) -> None:
    if not rows:
        summary.errors.append("no games loaded")
        return
    for row in rows:
        if row["home_team_id"] == row["visitor_team_id"]:
            summary.errors.append(f"game {row['external_id']} has identical home/away team")


async def run(
    client: BalldontlieClient,
    session: AsyncSession,
    *,
    seasons: list[int] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="sync_games")
    team_map = await load_team_map(session)

    rows: list[dict[str, Any]] = []
    async for raw in client.iter_games(seasons=seasons, start_date=start_date, end_date=end_date):
        try:
            game = RawGame.model_validate(raw)
        except ValidationError as exc:
            summary.rows_rejected += 1
            logger.warning("etl.row.rejected", job=summary.job, error=str(exc))
            continue

        home_id = team_map.get(game.home_team.id)
        visitor_id = team_map.get(game.visitor_team.id)
        if home_id is None or visitor_id is None:
            summary.rows_rejected += 1
            logger.warning(
                "etl.row.rejected",
                job=summary.job,
                reason="unknown team reference",
                external_id=game.id,
            )
            continue

        rows.append(_to_row(game, home_id, visitor_id))

    try:
        summary.rows_processed = await upsert(session, Game, rows, ["external_id"], UPDATE_COLS)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    _quality_checks(rows, summary)
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
