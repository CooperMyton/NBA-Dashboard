"""Game — one row per scheduled/played game. Scores are null until the game is final.

FKs to teams use RESTRICT: a game must never silently lose its teams. ``season`` is the
start year (2024 ⇒ 2024–25). See docs/decisions.md D-010.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class Game(TimestampMixin, Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[int] = mapped_column(unique=True, index=True)
    season: Mapped[int] = mapped_column(index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    postseason: Mapped[bool] = mapped_column(default=False)
    period: Mapped[int | None] = mapped_column()
    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    visitor_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    home_team_score: Mapped[int | None] = mapped_column()
    visitor_team_score: Mapped[int | None] = mapped_column()
