"""Team — the 30 NBA franchises. Natural key (abbreviation) kept distinct from the PK."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Provider (balldontlie) id, used as the idempotency key for upserts.
    external_id: Mapped[int] = mapped_column(unique=True, index=True)
    abbreviation: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(128))
    city: Mapped[str] = mapped_column(String(64))
    conference: Mapped[str] = mapped_column(String(16))
    division: Mapped[str] = mapped_column(String(32))
