"""Validation schemas for a raw balldontlie game payload."""

from pydantic import BaseModel, ConfigDict, Field


class RawTeamRef(BaseModel):
    """The nested team object inside a game payload; only the provider id is needed."""

    model_config = ConfigDict(extra="ignore")

    id: int


class RawGame(BaseModel):
    """A game as returned by the provider. Scores may be absent until the game is final."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    date: str
    season: int
    status: str
    period: int | None = None
    postseason: bool = False
    home_team_score: int | None = None
    visitor_team_score: int | None = None
    home_team: RawTeamRef
    visitor_team: RawTeamRef
    start_datetime: str | None = Field(default=None, alias="datetime")
