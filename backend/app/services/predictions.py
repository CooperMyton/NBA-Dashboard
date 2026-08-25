"""Prediction queries (populated once the ML pipeline lands in Phase 3)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.model_prediction import ModelPrediction
from backend.app.services.common import total_count


async def list_predictions(
    session: AsyncSession,
    *,
    page: Pagination,
    game_id: int | None = None,
    model_version: str | None = None,
    settled: bool | None = None,
) -> tuple[list[ModelPrediction], int]:
    stmt = select(ModelPrediction)
    if game_id is not None:
        stmt = stmt.where(ModelPrediction.game_id == game_id)
    if model_version is not None:
        stmt = stmt.where(ModelPrediction.model_version == model_version)
    if settled is True:
        stmt = stmt.where(ModelPrediction.settled_at.is_not(None))
    elif settled is False:
        stmt = stmt.where(ModelPrediction.settled_at.is_(None))
    total = await total_count(session, stmt)
    stmt = stmt.order_by(ModelPrediction.predicted_at.desc()).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total
