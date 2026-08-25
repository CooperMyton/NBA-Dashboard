"""Sync NBA teams from the provider into the ``teams`` table (idempotent).

Run as: ``python -m etl.jobs.sync_teams``
"""

import asyncio
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.team import Team
from etl.client.balldontlie import BalldontlieClient
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from etl.schemas.team import RawTeam

logger = get_logger("etl.sync_teams")

UPDATE_COLS = ["abbreviation", "name", "full_name", "city", "conference", "division"]

# The provider's /teams endpoint also returns international/exhibition teams (blank conference,
# non-unique abbreviations). We keep only the 30 NBA teams, identified by a real conference.
NBA_CONFERENCES = {"East", "West"}


def _to_row(team: RawTeam) -> dict[str, Any]:
    return {
        "external_id": team.id,
        "abbreviation": team.abbreviation,
        "name": team.name,
        "full_name": team.full_name,
        "city": team.city,
        "conference": team.conference,
        "division": team.division,
    }


def _quality_checks(rows: list[dict[str, Any]], summary: JobSummary) -> None:
    # Uniqueness of abbreviations is enforced by the DB constraint; here we guard against an
    # empty load, which signals an upstream/provider problem rather than a real "0 teams".
    if not rows:
        summary.errors.append("no teams loaded")


async def run(client: BalldontlieClient, session: AsyncSession) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="sync_teams")

    rows: list[dict[str, Any]] = []
    for raw in await client.list_teams():
        try:
            team = RawTeam.model_validate(raw)
        except ValidationError as exc:
            summary.rows_rejected += 1
            logger.warning("etl.row.rejected", job=summary.job, error=str(exc))
            continue
        if team.conference not in NBA_CONFERENCES:
            continue  # non-NBA (international/exhibition) team — skip
        rows.append(_to_row(team))

    try:
        summary.rows_processed = await upsert(session, Team, rows, ["external_id"], UPDATE_COLS)
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
    from etl.client.balldontlie import BalldontlieClient
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
