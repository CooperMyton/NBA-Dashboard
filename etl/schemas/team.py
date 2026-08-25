"""Validation schema for a raw balldontlie team payload."""

from pydantic import BaseModel, ConfigDict


class RawTeam(BaseModel):
    """A team as returned by the provider. Unknown fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    id: int
    abbreviation: str
    city: str
    conference: str
    division: str
    full_name: str
    name: str
