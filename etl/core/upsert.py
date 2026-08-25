"""Portable idempotent upsert (``INSERT ... ON CONFLICT DO UPDATE``).

Dispatches to the Postgres or SQLite dialect insert based on the session's bind, so the same
job code runs against production Postgres and the SQLite databases used in tests. This is what
makes re-running a job for the same data safe (spec's idempotency requirement).
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.base import Base


def _dialect_insert(dialect_name: str) -> Callable[..., Any]:
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        return pg_insert
    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        return sqlite_insert
    raise NotImplementedError(f"Upsert not supported for dialect: {dialect_name}")


# Postgres/asyncpg (and modern SQLite) cap a single statement's bind parameters. Keep each
# INSERT comfortably under that ceiling by chunking rows: params ≈ rows × columns.
_MAX_BIND_PARAMS = 30_000


async def upsert(
    session: AsyncSession,
    model: type[Base],
    rows: Sequence[Mapping[str, Any]],
    conflict_cols: Sequence[str],
    update_cols: Sequence[str],
    *,
    max_params: int = _MAX_BIND_PARAMS,
) -> int:
    """Insert ``rows``; on conflict over ``conflict_cols`` update ``update_cols``.

    Large batches are split into multiple INSERTs so no single statement exceeds the backend's
    bind-parameter limit (Postgres caps at 32767). All chunks run in the caller's transaction, so
    the load stays atomic. ``updated_at`` is always refreshed on update. Returns the row count sent.
    """
    materialized = list(rows)
    if not materialized:
        return 0

    insert = _dialect_insert(session.get_bind().dialect.name)
    columns_per_row = max(1, len(materialized[0]))
    chunk_size = max(1, max_params // columns_per_row)

    for start in range(0, len(materialized), chunk_size):
        batch = materialized[start : start + chunk_size]
        stmt = insert(model).values(batch)
        set_: dict[str, Any] = {col: getattr(stmt.excluded, col) for col in update_cols}
        set_["updated_at"] = func.current_timestamp()
        stmt = stmt.on_conflict_do_update(index_elements=list(conflict_cols), set_=set_)
        await session.execute(stmt)

    return len(materialized)
