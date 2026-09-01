"""PlayerInsight — a precomputed breakout or regression flag for a rostered player.

Computed by ``etl.jobs.sync_rosters`` rather than per request, mirroring ``season_projections``.
``detail`` carries the numbers behind the flag so the UI never shows a bare label.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class PlayerInsight(TimestampMixin, Base):
    __tablename__ = "player_insights"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "kind", name="uq_player_insights_player_season_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    score: Mapped[float] = mapped_column(Float)
    detail: Mapped[str] = mapped_column(String(256))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
