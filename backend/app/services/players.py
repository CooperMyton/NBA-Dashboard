"""Player queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.player import Player
from backend.app.services.common import total_count


async def list_players(
    session: AsyncSession,
    *,
    page: Pagination,
    team_id: int | None = None,
    search: str | None = None,
    active: bool | None = None,
) -> tuple[list[Player], int]:
    stmt = select(Player)
    if team_id is not None:
        stmt = stmt.where(Player.team_id == team_id)
    if search:
        stmt = stmt.where(Player.last_name.ilike(f"%{search}%"))
    if active:
        stmt = stmt.where(Player.roster_season.is_not(None))
    total = await total_count(session, stmt)
    stmt = stmt.order_by(Player.last_name, Player.first_name).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def get_player(session: AsyncSession, player_id: int) -> Player | None:
    return (
        await session.execute(select(Player).where(Player.id == player_id))
    ).scalar_one_or_none()
