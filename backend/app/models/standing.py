"""Standing — per-team, per-season standings DERIVED from games (docs/decisions.md D-004)."""

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class Standing(TimestampMixin, Base):
    __tablename__ = "standings"
    __table_args__ = (UniqueConstraint("season", "team_id", name="uq_standings_season_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    wins: Mapped[int] = mapped_column(default=0)
    losses: Mapped[int] = mapped_column(default=0)
    win_pct: Mapped[float] = mapped_column(Float, default=0.0)
    conference: Mapped[str | None] = mapped_column(String(16))
    conference_rank: Mapped[int | None] = mapped_column()
    home_record: Mapped[str | None] = mapped_column(String(16))
    road_record: Mapped[str | None] = mapped_column(String(16))
    streak: Mapped[str | None] = mapped_column(String(16))
