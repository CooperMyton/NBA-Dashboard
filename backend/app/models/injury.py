"""Injury — current player injury status.

Schema-only in v1: source data is paid-tier (docs/decisions.md D-006).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class Injury(TimestampMixin, Base):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str | None] = mapped_column(String(512))
    return_date: Mapped[date | None] = mapped_column(Date)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
