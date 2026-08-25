"""Prediction response schema."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int
    model_version: str
    predicted_home_win_prob: float
    predicted_home_win: bool
    actual_home_win: bool | None
    is_correct: bool | None
    predicted_at: datetime
    settled_at: datetime | None
