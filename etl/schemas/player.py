"""Validation schema for a raw balldontlie player payload."""

from pydantic import BaseModel, ConfigDict


class RawPlayerTeam(BaseModel):
    """Nested team object inside a player payload; only the provider id is used."""

    model_config = ConfigDict(extra="ignore")

    id: int


class RawPlayer(BaseModel):
    """A player as returned by the provider. ``team`` is absent for free agents."""

    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str
    last_name: str
    position: str | None = None
    height: str | None = None
    weight: str | None = None
    jersey_number: str | None = None
    college: str | None = None
    country: str | None = None
    team: RawPlayerTeam | None = None
