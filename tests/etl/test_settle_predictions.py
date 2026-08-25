"""Tests for the settle_predictions grading job."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.game import Game
from backend.app.models.model_prediction import ModelPrediction
from backend.app.models.team import Team
from etl.jobs import settle_predictions


async def _seed_final_game(session: AsyncSession) -> int:
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
    game = Game(
        external_id=1001,
        season=2023,
        game_date=date(2024, 1, 15),
        start_time=None,
        status="Final",
        postseason=False,
        period=4,
        home_team_id=home.id,
        visitor_team_id=away.id,
        home_team_score=110,
        visitor_team_score=104,  # home win
    )
    session.add(game)
    await session.flush()
    await session.commit()
    return game.id


async def test_settles_correct_and_incorrect_predictions(session: AsyncSession) -> None:
    game_id = await _seed_final_game(session)
    session.add_all(
        [
            ModelPrediction(
                game_id=game_id,
                model_version="v1",
                predicted_home_win_prob=0.7,
                predicted_home_win=True,
                predicted_at=datetime(2024, 1, 14, tzinfo=UTC),
            ),
            ModelPrediction(
                game_id=game_id,
                model_version="v2",
                predicted_home_win_prob=0.3,
                predicted_home_win=False,
                predicted_at=datetime(2024, 1, 14, tzinfo=UTC),
            ),
        ]
    )
    await session.commit()

    summary = await settle_predictions.run(session)
    assert summary.rows_processed == 2

    rows = {
        p.model_version: p for p in (await session.execute(select(ModelPrediction))).scalars().all()
    }
    # Home won: the True prediction is correct, the False one is not.
    assert rows["v1"].actual_home_win is True
    assert rows["v1"].is_correct is True
    assert rows["v1"].settled_at is not None
    assert rows["v2"].is_correct is False


async def test_settle_is_idempotent(session: AsyncSession) -> None:
    game_id = await _seed_final_game(session)
    session.add(
        ModelPrediction(
            game_id=game_id,
            model_version="v1",
            predicted_home_win_prob=0.7,
            predicted_home_win=True,
            predicted_at=datetime(2024, 1, 14, tzinfo=UTC),
        )
    )
    await session.commit()

    assert (await settle_predictions.run(session)).rows_processed == 1
    # Already settled -> nothing to do on the second run.
    assert (await settle_predictions.run(session)).rows_processed == 0
