"""Shared service helpers."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def total_count(session: AsyncSession, stmt: Select[Any]) -> int:
    """Count rows the (filtered) ``stmt`` would return, ignoring limit/offset."""
    count_stmt = select(func.count()).select_from(stmt.subquery())
    return (await session.execute(count_stmt)).scalar_one()
