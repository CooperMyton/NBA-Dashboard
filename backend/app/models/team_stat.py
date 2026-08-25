"""TeamStat — per-team, per-game line DERIVED from game scores (docs/decisions.md D-005).

CASCADE on game: a stat line is meaningless without its game.
"""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class TeamStat(TimestampMixin, Base):
    __tablename__ = "team_stats"
    __table_args__ = (UniqueConstraint("game_id", "team_id", name="uq_team_stats_game_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), index=True)
    season: Mapped[int] = mapped_column(index=True)
    is_home: Mapped[bool]
    points_for: Mapped[int]
    points_against: Mapped[int]
    won: Mapped[bool]
