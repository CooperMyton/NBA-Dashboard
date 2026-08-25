"""Shared reference-data lookups used across ETL jobs."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.team import Team


async def load_team_map(session: AsyncSession) -> dict[int, int]:
    """Return {provider team id -> surrogate team id} for FK resolution during load."""
    result = await session.execute(select(Team.external_id, Team.id))
    return dict(result.tuples().all())
