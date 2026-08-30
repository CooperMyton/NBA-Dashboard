"""SeasonProjection — Monte Carlo projection for one team in one season.

Written by ``etl.jobs.simulate_season``; read-only everywhere else. Percentages are 0-100.
``model_version`` matches ``model_predictions.model_version`` so projections can be traced to the
model that produced them.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class SeasonProjection(TimestampMixin, Base):
    __tablename__ = "season_projections"
    __table_args__ = (
        UniqueConstraint(
            "season", "team_id", "model_version", name="uq_season_projections_season_team_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)

    proj_wins: Mapped[float] = mapped_column(Float)
    proj_losses: Mapped[float] = mapped_column(Float)
    wins_p10: Mapped[float] = mapped_column(Float)
    wins_p50: Mapped[float] = mapped_column(Float)
    wins_p90: Mapped[float] = mapped_column(Float)

    make_playoffs_pct: Mapped[float] = mapped_column(Float)
    win_conference_pct: Mapped[float] = mapped_column(Float)
    win_title_pct: Mapped[float] = mapped_column(Float)
    avg_seed: Mapped[float] = mapped_column(Float)

    simulations: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
