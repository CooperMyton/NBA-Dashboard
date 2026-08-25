"""Team response schema."""

from pydantic import BaseModel, ConfigDict


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    abbreviation: str
    name: str
    full_name: str
    city: str
    conference: str
    division: str
