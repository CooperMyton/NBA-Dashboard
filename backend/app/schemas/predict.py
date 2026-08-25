"""Request/response schemas for POST /model/predict."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class PredictRequest(BaseModel):
    home_team_id: int
    visitor_team_id: int
    season: int
    game_date: date | None = None


class PredictResult(BaseModel):
    # ``model_version`` would collide with Pydantic's protected ``model_`` namespace.
    model_config = ConfigDict(protected_namespaces=())

    home_team_id: int
    visitor_team_id: int
    season: int
    game_date: date
    model_version: str
    predicted_home_win_prob: float
    predicted_home_win: bool
