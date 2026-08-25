"""Team routes (thin: parse → service → envelope)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import PaginationDep, SessionDep, build_meta, rate_limit
from backend.app.core.errors import not_found
from backend.app.schemas.envelope import Envelope, PagedEnvelope
from backend.app.schemas.team import TeamOut
from backend.app.services import teams as teams_service

router = APIRouter(prefix="/teams", tags=["teams"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=PagedEnvelope[TeamOut])
async def list_teams(
    session: SessionDep,
    page: PaginationDep,
    conference: Annotated[str | None, Query()] = None,
    sort: Annotated[str, Query()] = "abbreviation",
) -> PagedEnvelope[TeamOut]:
    items, total = await teams_service.list_teams(
        session, page=page, conference=conference, sort=sort
    )
    return PagedEnvelope[TeamOut](
        data=[TeamOut.model_validate(team) for team in items],
        meta=build_meta(total, page, len(items)),
    )


@router.get("/{team_id}", response_model=Envelope[TeamOut])
async def get_team(session: SessionDep, team_id: int) -> Envelope[TeamOut]:
    team = await teams_service.get_team(session, team_id)
    if team is None:
        raise not_found(f"Team {team_id} not found")
    return Envelope[TeamOut](data=TeamOut.model_validate(team))
