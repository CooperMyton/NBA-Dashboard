"""Season projection routes (read-through cached in Redis, per docs/decisions.md D-004/D-009)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, RedisDep, SessionDep, build_meta, rate_limit
from backend.app.core.cache import PROJECTIONS_PREFIX, cached_json
from backend.app.schemas.envelope import PagedEnvelope
from backend.app.schemas.projection import ProjectionOut
from backend.app.services import projections as projections_service

router = APIRouter(prefix="/projections", tags=["projections"], dependencies=[Depends(rate_limit)])

_CACHE_TTL_S = 300


@router.get("", response_model=PagedEnvelope[ProjectionOut])
async def list_projections(
    session: SessionDep,
    page: PaginationDep,
    redis: RedisDep,
    season: Annotated[int | None, Query()] = None,
) -> Any:
    key = f"{PROJECTIONS_PREFIX}{season}:{page.limit}:{page.offset}"

    async def producer() -> Any:
        items, total = await projections_service.list_projections(session, page=page, season=season)
        envelope = PagedEnvelope[ProjectionOut](
            data=[ProjectionOut.model_validate(row) for row in items],
            meta=build_meta(total, page, len(items)),
        )
        return envelope.model_dump(mode="json")

    return await cached_json(redis, key, _CACHE_TTL_S, producer)
