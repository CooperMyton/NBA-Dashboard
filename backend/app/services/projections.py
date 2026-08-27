"""Season projection queries.

Rows are written offline by ``etl.jobs.simulate_season``; this module only reads them.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.season_projection import SeasonProjection
from backend.app.services.common import total_count


async def list_projections(
    session: AsyncSession,
    *,
    page: Pagination,
    season: int | None = None,
) -> tuple[list[SeasonProjection], int]:
    stmt = select(SeasonProjection)
    if season is not None:
        stmt = stmt.where(SeasonProjection.season == season)
    total = await total_count(session, stmt)
    stmt = stmt.order_by(SeasonProjection.proj_wins.desc()).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total
