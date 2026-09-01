"""Player insight queries."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.team import Team
from backend.app.services.common import total_count


def _base(
    season: int, kind: str | None, team_id: int | None = None
) -> Select[tuple[PlayerInsight, Player, Team]]:
    stmt = (
        select(PlayerInsight, Player, Team)
        .join(Player, Player.id == PlayerInsight.player_id)
        .join(Team, Team.id == Player.team_id, isouter=True)
        .where(PlayerInsight.season == season)
        # Only players currently in the league are ever surfaced.
        .where(Player.roster_season.is_not(None))
    )
    if kind is not None:
        stmt = stmt.where(PlayerInsight.kind == kind)
    if team_id is not None:
        stmt = stmt.where(Player.team_id == team_id)
    return stmt


async def list_insights(
    session: AsyncSession,
    *,
    page: Pagination,
    season: int,
    kind: str | None = None,
    team_id: int | None = None,
) -> tuple[list[dict[str, object]], int]:
    stmt = _base(season, kind, team_id)
    total = await total_count(session, stmt)
    # Strongest signal first, regardless of sign — a big drop is as interesting as a big rise.
    stmt = stmt.order_by(func.abs(PlayerInsight.score).desc()).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "player_id": insight.player_id,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "team_id": player.team_id,
            "team_abbreviation": team.abbreviation if team is not None else None,
            "season": insight.season,
            "kind": insight.kind,
            "score": insight.score,
            "detail": insight.detail,
        }
        for insight, player, team in rows
    ], total
