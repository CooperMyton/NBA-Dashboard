"""Collect training data from PostgreSQL only — never the live provider (docs/ml_lifecycle.md).

Returns completed games (final, both scores present) as ``GameRecord``s in chronological order.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.game import Game
from ml.pipeline.features import GameRecord


async def collect_games(
    session: AsyncSession, *, seasons: list[int] | None = None
) -> list[GameRecord]:
    stmt = select(Game).where(
        Game.home_team_score.is_not(None),
        Game.visitor_team_score.is_not(None),
        func.lower(Game.status) == "final",
    )
    if seasons:
        stmt = stmt.where(Game.season.in_(seasons))
    rows = (await session.execute(stmt.order_by(Game.game_date, Game.id))).scalars().all()

    records: list[GameRecord] = []
    for game in rows:
        if game.home_team_score is None or game.visitor_team_score is None:
            continue  # unreachable given the filter, but narrows Optional for the type checker
        records.append(
            GameRecord(
                game_id=game.id,
                season=game.season,
                game_date=game.game_date,
                home_team_id=game.home_team_id,
                visitor_team_id=game.visitor_team_id,
                home_score=game.home_team_score,
                visitor_score=game.visitor_team_score,
            )
        )
    return records
