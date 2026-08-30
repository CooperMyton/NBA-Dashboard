"""Player — roster/bio data. FK to team is SET NULL: a player outlives a team change."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class Player(TimestampMixin, Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[int] = mapped_column(unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64), index=True)
    position: Mapped[str | None] = mapped_column(String(8))
    height: Mapped[str | None] = mapped_column(String(8))
    weight: Mapped[str | None] = mapped_column(String(8))
    jersey_number: Mapped[str | None] = mapped_column(String(8))
    college: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(64))
    # NBA's own player id, populated by the roster sync. Lets later syncs join on a stable key
    # instead of repeating name matching.
    nba_player_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    # The season this player is rostered for (start-year convention). Null for historical players.
    roster_season: Mapped[int | None] = mapped_column(index=True)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
