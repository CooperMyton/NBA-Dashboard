"""Game response schema."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    game_date: date
    start_time: datetime | None
    status: str
    postseason: bool
    period: int | None
    home_team_id: int
    visitor_team_id: int
    home_team_score: int | None
    visitor_team_score: int | None
