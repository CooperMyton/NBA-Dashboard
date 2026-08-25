"""Tests for collecting training data from the database."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.game import Game
from backend.app.models.team import Team
from ml.pipeline.collect import collect_games


async def test_collect_returns_only_completed_games(session: AsyncSession) -> None:
    home = Team(
        external_id=1,
        abbreviation="BOS",
        name="Celtics",
        full_name="Boston Celtics",
        city="Boston",
        conference="East",
        division="Atlantic",
    )
    away = Team(
        external_id=2,
        abbreviation="LAL",
        name="Lakers",
        full_name="Los Angeles Lakers",
        city="Los Angeles",
        conference="West",
        division="Pacific",
    )
    session.add_all([home, away])
    await session.flush()

    session.add_all(
        [
            Game(
                external_id=1,
                season=2023,
                game_date=date(2024, 1, 1),
                start_time=None,
                status="Final",
                postseason=False,
                period=4,
                home_team_id=home.id,
                visitor_team_id=away.id,
                home_team_score=110,
                visitor_team_score=104,
            ),
            Game(  # scheduled, no scores -> excluded
                external_id=2,
                season=2023,
                game_date=date(2024, 2, 1),
                start_time=None,
                status="scheduled",
                postseason=False,
                period=None,
                home_team_id=away.id,
                visitor_team_id=home.id,
                home_team_score=None,
                visitor_team_score=None,
            ),
        ]
    )
    await session.commit()

    records = await collect_games(session)
    assert len(records) == 1
    assert records[0].home_score == 110
    assert records[0].home_won == 1
