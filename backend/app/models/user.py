"""User — holds a hashed API key for POST /model/predict auth (docs/decisions.md D-007).

UUID PK (the only externally-referenced entity). Keys are minted by an admin CLI; there is
no public registration.
"""

import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    api_key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
