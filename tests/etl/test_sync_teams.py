"""Tests for the sync_teams job: load, idempotency, upsert-update, and rejection."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.team import Team
from etl.jobs import sync_teams
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


async def _team_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Team))).scalar_one()


async def test_loads_teams_and_is_idempotent(session: AsyncSession) -> None:
    teams = load_fixture("teams.json")
    client = FakeClient(teams=teams)

    first = await sync_teams.run(client, session)  # type: ignore[arg-type]
    assert first.rows_processed == len(teams)
    assert first.rows_rejected == 0
    assert first.errors == []
    assert await _team_count(session) == len(teams)

    # Running again must not duplicate rows.
    await sync_teams.run(client, session)  # type: ignore[arg-type]
    assert await _team_count(session) == len(teams)


async def test_upsert_updates_changed_fields(session: AsyncSession) -> None:
    teams = load_fixture("teams.json")
    await sync_teams.run(FakeClient(teams=teams), session)  # type: ignore[arg-type]

    teams[0]["city"] = "Relocated City"
    await sync_teams.run(FakeClient(teams=teams), session)  # type: ignore[arg-type]

    team = (
        await session.execute(select(Team).where(Team.external_id == teams[0]["id"]))
    ).scalar_one()
    assert team.city == "Relocated City"


async def test_rejects_invalid_payload(session: AsyncSession) -> None:
    teams = [
        load_fixture("teams.json")[0],
        {"id": 3, "abbreviation": "NYK"},  # missing required fields
    ]
    summary = await sync_teams.run(FakeClient(teams=teams), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 1
    assert summary.rows_rejected == 1
    assert await _team_count(session) == 1


async def test_empty_load_flags_data_quality_error(session: AsyncSession) -> None:
    summary = await sync_teams.run(FakeClient(teams=[]), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 0
    assert summary.errors == ["no teams loaded"]


async def test_filters_out_non_nba_teams(session: AsyncSession) -> None:
    # The provider returns international teams with blank conferences (and clashing abbreviations).
    teams = [
        load_fixture("teams.json")[0],  # NBA team (conference "East")
        {
            "id": 216597,
            "abbreviation": "LON",
            "city": "London",
            "conference": "",
            "division": "",
            "full_name": "London Lions",
            "name": "Lions",
        },
    ]
    summary = await sync_teams.run(FakeClient(teams=teams), session)  # type: ignore[arg-type]

    assert summary.rows_processed == 1  # only the NBA team is loaded
    assert summary.rows_rejected == 0  # non-NBA teams are skipped, not validation failures
    assert await _team_count(session) == 1
