"""Tests for the predict_upcoming batch inference job."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.game import Game
from backend.app.models.model_prediction import ModelPrediction
from backend.app.models.team import Team
from etl.jobs import predict_upcoming
from ml.pipeline.features import FEATURE_NAMES, build_training_data
from ml.pipeline.inference import Predictor
from ml.pipeline.train import train_model
from tests.ml.synth import synth_game_records


def _predictor() -> Predictor:
    features, labels, _ = build_training_data(synth_game_records())
    model = train_model(features, labels)
    return Predictor(model, version=1, feature_names=FEATURE_NAMES, model_version="test-model")


async def _seed_upcoming_game(session: AsyncSession) -> int:
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
        external_id=2001,
        season=2023,
        game_date=date(2024, 3, 1),
        start_time=None,
        status="scheduled",
        postseason=False,
        period=None,
        home_team_id=home.id,
        visitor_team_id=away.id,
        home_team_score=None,
        visitor_team_score=None,  # unplayed
    )
    session.add(game)
    await session.flush()
    await session.commit()
    return game.id


async def test_predicts_upcoming_game_and_is_idempotent(session: AsyncSession) -> None:
    game_id = await _seed_upcoming_game(session)

    summary = await predict_upcoming.run(session, _predictor())
    assert summary.rows_processed == 1

    prediction = (
        await session.execute(select(ModelPrediction).where(ModelPrediction.game_id == game_id))
    ).scalar_one()
    assert prediction.model_version == "test-model"
    assert 0.0 <= prediction.predicted_home_win_prob <= 1.0
    assert prediction.settled_at is None

    # Re-running refreshes rather than duplicating.
    await predict_upcoming.run(session, _predictor())
    total = (await session.execute(select(func.count()).select_from(ModelPrediction))).scalar_one()
    assert total == 1


async def test_no_active_model_is_a_no_op(session: AsyncSession) -> None:
    await _seed_upcoming_game(session)
    summary = await predict_upcoming.run(session, None)
    assert summary.rows_processed == 0
    assert summary.errors == []
    total = (await session.execute(select(func.count()).select_from(ModelPrediction))).scalar_one()
    assert total == 0
