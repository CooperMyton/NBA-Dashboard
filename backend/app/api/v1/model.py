"""Model routes: authenticated inference and manual model reload.

``POST /model/predict`` requires a valid ``X-API-Key`` (spec) and reads the active model only.
"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.api.deps import ActiveModelDep, ApiKeyDep, SessionDep, rate_limit
from backend.app.schemas.envelope import Envelope
from backend.app.schemas.predict import PredictRequest, PredictResult
from backend.app.services import model_predict
from ml.pipeline.registry import load_registry

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/registry", dependencies=[Depends(rate_limit)])
async def registry() -> dict[str, Any]:
    """Public, read-only view of registered model versions + the active pointer."""
    return {"data": load_registry()}


@router.post("/predict", response_model=Envelope[PredictResult])
async def predict(
    body: PredictRequest,
    session: SessionDep,
    active: ActiveModelDep,
    _user: ApiKeyDep,
) -> Any:
    result = await model_predict.predict_home_win(
        session,
        active,
        home_team_id=body.home_team_id,
        visitor_team_id=body.visitor_team_id,
        season=body.season,
        game_date=body.game_date,
    )
    return Envelope[PredictResult](data=PredictResult(**result)).model_dump(mode="json")


@router.post("/reload")
async def reload_model(active: ActiveModelDep, _user: ApiKeyDep) -> dict[str, Any]:
    active.load()
    version = active.predictor.model_version if active.predictor else None
    return {"data": {"reloaded": True, "active_model": version}}
