"""End-to-end training run against a seeded database."""

import pathlib

from sqlalchemy.ext.asyncio import AsyncSession

from ml.pipeline.registry import active_entry, load_registry
from ml.pipeline.run_training import run_training
from tests.ml.synth import seed_synthetic_db, synth_game_records


async def test_run_training_registers_and_promotes_winner(
    session: AsyncSession, tmp_path: pathlib.Path
) -> None:
    await seed_synthetic_db(session, synth_game_records())
    registry_path = tmp_path / "registry.json"
    models_dir = tmp_path / "models"

    result = await run_training(
        session,
        date_str="20240101",
        git_commit="abc123",
        promote=True,
        registry_path=registry_path,
        models_dir=models_dir,
    )

    assert result["beats_baseline"] is True
    # Both candidate algorithms were evaluated.
    assert {c["algorithm"] for c in result["candidates"]} == {
        "logistic_regression",
        "gradient_boosting",
    }
    assert len(result["registered"]) >= 1
    assert result["active_version"] is not None
    best = result["best"]
    assert (models_dir / best["filename"]).exists()
    assert best["algorithm"] in {"logistic_regression", "gradient_boosting"}

    # Promotion set the active pointer to the best model, and metadata round-trips.
    registry = load_registry(registry_path)
    assert registry["active"] == result["active_version"]
    entry = active_entry(registry_path)
    assert entry is not None
    assert entry["features"]  # feature list recorded
    assert entry["git_commit"] == "abc123"


async def test_run_training_insufficient_data_does_not_register(
    session: AsyncSession, tmp_path: pathlib.Path
) -> None:
    await seed_synthetic_db(session, synth_game_records(rounds=1))  # only 6 games
    registry_path = tmp_path / "registry.json"

    result = await run_training(
        session, date_str="20240101", registry_path=registry_path, models_dir=tmp_path / "m"
    )

    assert result["beats_baseline"] is False
    assert result.get("insufficient_data") is True
    assert not registry_path.exists()
