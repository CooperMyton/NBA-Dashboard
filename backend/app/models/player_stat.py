"""PlayerStat — per-player, per-game box score.

Schema-only in v1: source data is paid-tier (docs/decisions.md D-006). CASCADE on both
player and game — a box-score line has no meaning without either.
"""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class PlayerStat(TimestampMixin, Base):
    __tablename__ = "player_stats"
    __table_args__ = (UniqueConstraint("player_id", "game_id", name="uq_player_stats_player_game"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    season: Mapped[int] = mapped_column(index=True)
    minutes: Mapped[str | None] = mapped_column(String(8))
    points: Mapped[int | None] = mapped_column()
    rebounds: Mapped[int | None] = mapped_column()
    assists: Mapped[int | None] = mapped_column()
    steals: Mapped[int | None] = mapped_column()
    blocks: Mapped[int | None] = mapped_column()
    turnovers: Mapped[int | None] = mapped_column()
    fgm: Mapped[int | None] = mapped_column()
    fga: Mapped[int | None] = mapped_column()
    fg3m: Mapped[int | None] = mapped_column()
    fg3a: Mapped[int | None] = mapped_column()
    ftm: Mapped[int | None] = mapped_column()
    fta: Mapped[int | None] = mapped_column()
