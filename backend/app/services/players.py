"""Player queries."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.player import Player
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.services.common import total_count

PlayerWithStats = tuple[Player, PlayerSeasonStat | None]


async def _latest_stats_by_player(
    session: AsyncSession, player_ids: list[int]
) -> dict[int, PlayerSeasonStat]:
    """Fetch every stat row for the given players in ONE query and keep each player's most
    recent season line.

    Ordering by season descending means the first row seen for a given player is already its
    highest season, so a single pass over the (already-sorted) result set picks it out — no
    per-player follow-up query needed.
    """
    if not player_ids:
        return {}
    stmt = (
        select(PlayerSeasonStat)
        .where(PlayerSeasonStat.player_id.in_(player_ids))
        .order_by(PlayerSeasonStat.player_id, PlayerSeasonStat.season.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    latest: dict[int, PlayerSeasonStat] = {}
    for stat in rows:
        latest.setdefault(stat.player_id, stat)
    return latest


async def list_players(
    session: AsyncSession,
    *,
    page: Pagination,
    team_id: int | None = None,
    search: str | None = None,
    active: bool | None = None,
) -> tuple[list[PlayerWithStats], int]:
    stmt = select(Player)
    if team_id is not None:
        stmt = stmt.where(Player.team_id == team_id)
    if search:
        stmt = stmt.where(Player.last_name.ilike(f"%{search}%"))
    if active:
        stmt = stmt.where(Player.roster_season.is_not(None))
    total = await total_count(session, stmt)
    stmt = stmt.order_by(Player.last_name, Player.first_name).limit(page.limit).offset(page.offset)
    players = list((await session.execute(stmt)).scalars().all())
    latest = await _latest_stats_by_player(session, [player.id for player in players])
    return [(player, latest.get(player.id)) for player in players], total


async def get_player(session: AsyncSession, player_id: int) -> PlayerWithStats | None:
    player = (
        await session.execute(select(Player).where(Player.id == player_id))
    ).scalar_one_or_none()
    if player is None:
        return None
    latest = await _latest_stats_by_player(session, [player.id])
    return player, latest.get(player.id)
