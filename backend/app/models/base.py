"""Declarative base and shared mixins for all ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TimestampMixin:
    """Adds server-managed UTC ``created_at`` / ``updated_at`` columns.

    Every table carries these per the spec's Database rules. ``CURRENT_TIMESTAMP`` is used
    (rather than ``now()``) as the SQL-standard, portable server default.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )
