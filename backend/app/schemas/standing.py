"""Standing response schema."""

from pydantic import BaseModel, ConfigDict


class StandingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    team_id: int
    wins: int
    losses: int
    win_pct: float
    conference: str | None
    conference_rank: int | None
    home_record: str | None
    road_record: str | None
    streak: str | None
