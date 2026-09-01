"""PlayerSeasonStat — one aggregated season line per player.

Sourced from nba_api's league dashboards (docs/decisions.md D-006 covers why the per-game
``player_stats`` table stays empty: box scores are paid-tier on balldontlie).
"""

from sqlalchemy import Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class PlayerSeasonStat(TimestampMixin, Base):
    __tablename__ = "player_season_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_stats_player_season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(index=True)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    games_played: Mapped[int] = mapped_column()
    minutes: Mapped[float] = mapped_column(Float)
    points: Mapped[float] = mapped_column(Float)
    rebounds: Mapped[float] = mapped_column(Float)
    assists: Mapped[float] = mapped_column(Float)
    fg3_pct: Mapped[float] = mapped_column(Float)
    fg3a: Mapped[float] = mapped_column(Float)
    ts_pct: Mapped[float] = mapped_column(Float)
    usage_pct: Mapped[float] = mapped_column(Float)
