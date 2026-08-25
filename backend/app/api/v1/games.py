"""Game routes."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, SessionDep, build_meta, rate_limit
from backend.app.core.errors import not_found
from backend.app.schemas.envelope import Envelope, PagedEnvelope
from backend.app.schemas.game import GameOut
from backend.app.services import games as games_service

router = APIRouter(prefix="/games", tags=["games"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=PagedEnvelope[GameOut])
async def list_games(
    session: SessionDep,
    page: PaginationDep,
    season: Annotated[int | None, Query()] = None,
    team_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> PagedEnvelope[GameOut]:
    items, total = await games_service.list_games(
        session,
        page=page,
        season=season,
        team_id=team_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        order=order,
    )
    return PagedEnvelope[GameOut](
        data=[GameOut.model_validate(game) for game in items],
        meta=build_meta(total, page, len(items)),
    )


@router.get("/{game_id}", response_model=Envelope[GameOut])
async def get_game(session: SessionDep, game_id: int) -> Envelope[GameOut]:
    game = await games_service.get_game(session, game_id)
    if game is None:
        raise not_found(f"Game {game_id} not found")
    return Envelope[GameOut](data=GameOut.model_validate(game))
