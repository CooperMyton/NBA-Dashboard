"""Season projection response schema."""

from pydantic import BaseModel, ConfigDict


class ProjectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    team_id: int
    model_version: str
    proj_wins: float
    proj_losses: float
    wins_p10: float
    wins_p50: float
    wins_p90: float
    make_playoffs_pct: float
    win_conference_pct: float
    win_title_pct: float
    avg_seed: float
    simulations: int
