"""Standings queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.standing import Standing
from backend.app.services.common import total_count


async def list_standings(
    session: AsyncSession,
    *,
    page: Pagination,
    season: int | None = None,
    conference: str | None = None,
) -> tuple[list[Standing], int]:
    stmt = select(Standing)
    if season is not None:
        stmt = stmt.where(Standing.season == season)
    if conference is not None:
        stmt = stmt.where(Standing.conference == conference)
    total = await total_count(session, stmt)
    stmt = (
        stmt.order_by(Standing.conference, Standing.conference_rank, Standing.win_pct.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total
