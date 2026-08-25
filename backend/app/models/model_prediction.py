"""ModelPrediction — a model's prediction for a game, later settled against the result.

``model_version`` references a registry entry by string (artifacts are file-based, not rows).
``actual_home_win`` / ``is_correct`` / ``settled_at`` are filled by the grading job
(docs/decisions.md D-008).
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class ModelPrediction(TimestampMixin, Base):
    __tablename__ = "model_predictions"
    __table_args__ = (
        UniqueConstraint("game_id", "model_version", name="uq_model_predictions_game_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)
    predicted_home_win_prob: Mapped[float] = mapped_column(Float)
    predicted_home_win: Mapped[bool]
    actual_home_win: Mapped[bool | None] = mapped_column()
    is_correct: Mapped[bool | None] = mapped_column()
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
