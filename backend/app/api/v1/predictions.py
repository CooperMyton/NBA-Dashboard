"""Prediction routes (read-through cached; populated by the ML pipeline in Phase 3)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, RedisDep, SessionDep, build_meta, rate_limit
from backend.app.core.cache import PREDICTIONS_PREFIX, cached_json
from backend.app.schemas.envelope import PagedEnvelope
from backend.app.schemas.prediction import PredictionOut
from backend.app.services import predictions as predictions_service

router = APIRouter(prefix="/predictions", tags=["predictions"], dependencies=[Depends(rate_limit)])

_CACHE_TTL_S = 300


@router.get("", response_model=PagedEnvelope[PredictionOut])
async def list_predictions(
    session: SessionDep,
    page: PaginationDep,
    redis: RedisDep,
    game_id: Annotated[int | None, Query()] = None,
    model_version: Annotated[str | None, Query()] = None,
    settled: Annotated[bool | None, Query()] = None,
) -> Any:
    key = f"{PREDICTIONS_PREFIX}{game_id}:{model_version}:{settled}:{page.limit}:{page.offset}"

    async def producer() -> Any:
        items, total = await predictions_service.list_predictions(
            session, page=page, game_id=game_id, model_version=model_version, settled=settled
        )
        envelope = PagedEnvelope[PredictionOut](
            data=[PredictionOut.model_validate(row) for row in items],
            meta=build_meta(total, page, len(items)),
        )
        return envelope.model_dump(mode="json")

    return await cached_json(redis, key, _CACHE_TTL_S, producer)
