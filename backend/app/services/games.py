"""Game queries."""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.game import Game
from backend.app.services.common import total_count


async def list_games(
    session: AsyncSession,
    *,
    page: Pagination,
    season: int | None = None,
    team_id: int | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    order: str = "desc",
) -> tuple[list[Game], int]:
    stmt = select(Game)
    if season is not None:
        stmt = stmt.where(Game.season == season)
    if team_id is not None:
        stmt = stmt.where(or_(Game.home_team_id == team_id, Game.visitor_team_id == team_id))
    if status is not None:
        stmt = stmt.where(Game.status == status)
    if start_date is not None:
        stmt = stmt.where(Game.game_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Game.game_date <= end_date)

    total = await total_count(session, stmt)
    order_col = Game.game_date.asc() if order == "asc" else Game.game_date.desc()
    stmt = stmt.order_by(order_col, Game.id).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def get_game(session: AsyncSession, game_id: int) -> Game | None:
    return (await session.execute(select(Game).where(Game.id == game_id))).scalar_one_or_none()
