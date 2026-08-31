"""Player routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, SessionDep, build_meta, rate_limit
from backend.app.core.errors import not_found
from backend.app.models.player import Player
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.schemas.envelope import Envelope, PagedEnvelope
from backend.app.schemas.player import PlayerOut, PlayerSeasonStatOut
from backend.app.schemas.player_insight import PlayerInsightOut
from backend.app.services import player_insights as player_insights_service
from backend.app.services import players as players_service

router = APIRouter(prefix="/players", tags=["players"], dependencies=[Depends(rate_limit)])


def _to_player_out(player: Player, stat: PlayerSeasonStat | None) -> PlayerOut:
    latest_stats = PlayerSeasonStatOut.model_validate(stat) if stat is not None else None
    return PlayerOut.model_validate(player).model_copy(update={"latest_stats": latest_stats})


@router.get("", response_model=PagedEnvelope[PlayerOut])
async def list_players(
    session: SessionDep,
    page: PaginationDep,
    team_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    active: Annotated[bool | None, Query()] = None,
) -> PagedEnvelope[PlayerOut]:
    items, total = await players_service.list_players(
        session, page=page, team_id=team_id, search=search, active=active
    )
    return PagedEnvelope[PlayerOut](
        data=[_to_player_out(player, stat) for player, stat in items],
        meta=build_meta(total, page, len(items)),
    )


# Must be declared before `/{player_id}` — FastAPI matches routes in declaration order, and
# below it "/players/insights" would be routed here with "insights" failing to parse as an int.
@router.get("/insights", response_model=PagedEnvelope[PlayerInsightOut])
async def list_player_insights(
    session: SessionDep,
    page: PaginationDep,
    season: Annotated[int, Query()],
    kind: Annotated[str | None, Query(pattern="^(breakout|regression)$")] = None,
) -> PagedEnvelope[PlayerInsightOut]:
    items, total = await player_insights_service.list_insights(
        session, page=page, season=season, kind=kind
    )
    return PagedEnvelope[PlayerInsightOut](
        data=[PlayerInsightOut.model_validate(row) for row in items],
        meta=build_meta(total, page, len(items)),
    )


@router.get("/{player_id}", response_model=Envelope[PlayerOut])
async def get_player(session: SessionDep, player_id: int) -> Envelope[PlayerOut]:
    result = await players_service.get_player(session, player_id)
    if result is None:
        raise not_found(f"Player {player_id} not found")
    player, stat = result
    return Envelope[PlayerOut](data=_to_player_out(player, stat))
