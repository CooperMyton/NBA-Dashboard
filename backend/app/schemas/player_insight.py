"""Player insight response schema."""

from pydantic import BaseModel, ConfigDict


class PlayerInsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    first_name: str
    last_name: str
    team_id: int | None
    team_abbreviation: str | None
    season: int
    kind: str
    score: float
    detail: str
