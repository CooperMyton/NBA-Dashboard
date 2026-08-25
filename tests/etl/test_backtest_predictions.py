"""Tests for the backtest_predictions job."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.model_prediction import ModelPrediction
from etl.jobs import backtest_predictions
from ml.pipeline.features import FEATURE_NAMES, build_training_data
from ml.pipeline.inference import Predictor
from ml.pipeline.train import train_model
from tests.ml.synth import seed_synthetic_db, synth_game_records


def _predictor() -> Predictor:
    features, labels, _ = build_training_data(synth_game_records())
    model = train_model(features, labels)
    return Predictor(model, version=1, feature_names=FEATURE_NAMES, model_version="backtest-v1")


async def test_backtest_records_settled_predictions(session: AsyncSession) -> None:
    records = synth_game_records()
    await seed_synthetic_db(session, records)

    summary = await backtest_predictions.run(session, _predictor(), seasons=[2023])
    assert summary.rows_processed == len(records)

    predictions = (await session.execute(select(ModelPrediction))).scalars().all()
    assert len(predictions) == len(records)
    # Every backtested prediction is settled (has an actual outcome + correctness).
    assert all(p.settled_at is not None for p in predictions)
    assert all(p.actual_home_win is not None for p in predictions)
    assert all(p.is_correct is not None for p in predictions)

    # Re-running refreshes rather than duplicating.
    await backtest_predictions.run(session, _predictor(), seasons=[2023])
    total = (await session.execute(select(func.count()).select_from(ModelPrediction))).scalar_one()
    assert total == len(records)


async def test_backtest_no_model_is_a_no_op(session: AsyncSession) -> None:
    await seed_synthetic_db(session, synth_game_records(rounds=1))
    summary = await backtest_predictions.run(session, None, seasons=[2023])
    assert summary.rows_processed == 0
    total = (await session.execute(select(func.count()).select_from(ModelPrediction))).scalar_one()
    assert total == 0
