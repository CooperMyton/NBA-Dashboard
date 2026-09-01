"""Player response schema."""

from pydantic import BaseModel, ConfigDict


class PlayerSeasonStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    ts_pct: float
    usage_pct: float


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    position: str | None
    height: str | None
    weight: str | None
    jersey_number: str | None
    college: str | None
    country: str | None
    team_id: int | None
    roster_season: int | None = None
    latest_stats: PlayerSeasonStatOut | None = None
