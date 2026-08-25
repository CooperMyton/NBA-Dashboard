"""Standings routes (read-through cached in Redis, per docs/decisions.md D-004/D-009)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, RedisDep, SessionDep, build_meta, rate_limit
from backend.app.core.cache import STANDINGS_PREFIX, cached_json
from backend.app.schemas.envelope import PagedEnvelope
from backend.app.schemas.standing import StandingOut
from backend.app.services import standings as standings_service

router = APIRouter(prefix="/standings", tags=["standings"], dependencies=[Depends(rate_limit)])

_CACHE_TTL_S = 300


@router.get("", response_model=PagedEnvelope[StandingOut])
async def list_standings(
    session: SessionDep,
    page: PaginationDep,
    redis: RedisDep,
    season: Annotated[int | None, Query()] = None,
    conference: Annotated[str | None, Query()] = None,
) -> Any:
    key = f"{STANDINGS_PREFIX}{season}:{conference}:{page.limit}:{page.offset}"

    async def producer() -> Any:
        items, total = await standings_service.list_standings(
            session, page=page, season=season, conference=conference
        )
        envelope = PagedEnvelope[StandingOut](
            data=[StandingOut.model_validate(row) for row in items],
            meta=build_meta(total, page, len(items)),
        )
        return envelope.model_dump(mode="json")

    return await cached_json(redis, key, _CACHE_TTL_S, producer)
