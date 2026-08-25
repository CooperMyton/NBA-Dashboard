"""Tests for model loading and matchup feature construction at inference time."""

import pathlib
from datetime import date

from ml.pipeline.features import FEATURE_NAMES, GameRecord, build_training_data
from ml.pipeline.inference import features_for_matchup, load_active_predictor
from ml.pipeline.registry import register_model, set_active
from ml.pipeline.train import train_model
from tests.ml.synth import synth_game_records


def test_load_active_predictor_round_trip(tmp_path: pathlib.Path) -> None:
    registry_path = tmp_path / "registry.json"
    models_dir = tmp_path / "models"

    features, labels, _ = build_training_data(synth_game_records())
    model = train_model(features, labels)
    entry = register_model(
        model,
        metrics={"accuracy": 0.6},
        feature_names=FEATURE_NAMES,
        training_window={"seasons": [2023]},
        date_str="20240101",
        git_commit="abc",
        registry_path=registry_path,
        models_dir=models_dir,
    )

    assert load_active_predictor(registry_path, models_dir) is None  # nothing active yet

    set_active(entry["version"], registry_path)
    predictor = load_active_predictor(registry_path, models_dir)
    assert predictor is not None
    assert predictor.model_version == entry["filename"]
    probs = predictor.predict_proba([dict.fromkeys(FEATURE_NAMES, 0.0)])
    assert len(probs) == 1
    assert 0.0 <= probs[0] <= 1.0


def test_features_for_matchup_ignores_games_on_or_after_target_date() -> None:
    history = [
        GameRecord(1, 2023, date(2024, 1, 1), 10, 20, 100, 90),  # before -> counted
        GameRecord(2, 2023, date(2024, 1, 5), 10, 20, 80, 100),  # on/after -> ignored
    ]
    row = features_for_matchup(history, 2023, date(2024, 1, 5), home_id=10, away_id=20)
    # Only game 1 seen: team 10 is 1-0, so as home its form win pct is 1.0.
    assert row["home_form_win_pct"] == 1.0
    assert row["h2h_home_win_pct"] == 1.0
