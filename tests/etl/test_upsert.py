"""Tests for the chunked idempotent upsert."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.team import Team
from etl.core.upsert import upsert

UPDATE_COLS = ["abbreviation", "name", "full_name", "city", "conference", "division"]


def _team_rows(n: int) -> list[dict[str, object]]:
    return [
        {
            "external_id": i,
            "abbreviation": f"T{i:03d}",
            "name": f"Team {i}",
            "full_name": f"Team {i} Full",
            "city": "City",
            "conference": "East" if i % 2 else "West",
            "division": "Div",
        }
        for i in range(1, n + 1)
    ]


async def _count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Team))).scalar_one()


async def test_upsert_chunks_large_batches(session: AsyncSession) -> None:
    rows = _team_rows(50)
    # max_params=20 over 7 columns -> chunk size 2 -> 25 separate INSERTs.
    processed = await upsert(session, Team, rows, ["external_id"], UPDATE_COLS, max_params=20)
    await session.commit()

    assert processed == 50
    assert await _count(session) == 50


async def test_upsert_is_idempotent_across_chunks(session: AsyncSession) -> None:
    rows = _team_rows(30)
    await upsert(session, Team, rows, ["external_id"], UPDATE_COLS, max_params=20)
    await session.commit()

    # Re-run with a changed field: still 30 rows, and the update applied.
    rows[0]["city"] = "Relocated"
    await upsert(session, Team, rows, ["external_id"], UPDATE_COLS, max_params=20)
    await session.commit()

    assert await _count(session) == 30
    team = (await session.execute(select(Team).where(Team.external_id == 1))).scalar_one()
    assert team.city == "Relocated"
