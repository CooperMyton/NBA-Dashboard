"""Player routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, SessionDep, build_meta, rate_limit
from backend.app.core.errors import not_found
from backend.app.schemas.envelope import Envelope, PagedEnvelope
from backend.app.schemas.player import PlayerOut
from backend.app.services import players as players_service

router = APIRouter(prefix="/players", tags=["players"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=PagedEnvelope[PlayerOut])
async def list_players(
    session: SessionDep,
    page: PaginationDep,
    team_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> PagedEnvelope[PlayerOut]:
    items, total = await players_service.list_players(
        session, page=page, team_id=team_id, search=search
    )
    return PagedEnvelope[PlayerOut](
        data=[PlayerOut.model_validate(player) for player in items],
        meta=build_meta(total, page, len(items)),
    )


@router.get("/{player_id}", response_model=Envelope[PlayerOut])
async def get_player(session: SessionDep, player_id: int) -> Envelope[PlayerOut]:
    player = await players_service.get_player(session, player_id)
    if player is None:
        raise not_found(f"Player {player_id} not found")
    return Envelope[PlayerOut](data=PlayerOut.model_validate(player))
