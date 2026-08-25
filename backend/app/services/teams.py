"""Team queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.team import Team
from backend.app.services.common import total_count

_SORTS = {
    "abbreviation": Team.abbreviation,
    "full_name": Team.full_name,
    "city": Team.city,
}


async def list_teams(
    session: AsyncSession,
    *,
    page: Pagination,
    conference: str | None = None,
    sort: str = "abbreviation",
) -> tuple[list[Team], int]:
    stmt = select(Team)
    if conference is not None:
        stmt = stmt.where(Team.conference == conference)
    total = await total_count(session, stmt)
    order_col = _SORTS.get(sort, Team.abbreviation)
    stmt = stmt.order_by(order_col).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def get_team(session: AsyncSession, team_id: int) -> Team | None:
    return (await session.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
