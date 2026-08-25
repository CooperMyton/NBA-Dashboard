"""Inference: load the active registered model and compute features for a single matchup.

The API loads the active model once (startup / manual reload) and calls ``predict_proba`` — it
never retrains or loads per request (docs/ml_lifecycle.md). Matchup features are built from prior
completed games only, mirroring training (no leakage).
"""

from datetime import date
from pathlib import Path
from typing import Any

import joblib

from ml.pipeline.features import FeatureBuilder, GameRecord
from ml.pipeline.registry import MODELS_DIR, REGISTRY_PATH, active_entry
from ml.pipeline.train import to_matrix


class Predictor:
    def __init__(
        self, model: Any, *, version: int, feature_names: list[str], model_version: str
    ) -> None:
        self._model = model
        self.version = version
        self.feature_names = feature_names
        self.model_version = model_version

    def predict_proba(self, rows: list[dict[str, float]]) -> list[float]:
        probabilities = self._model.predict_proba(to_matrix(rows, self.feature_names))[:, 1]
        return [float(p) for p in probabilities]


def load_active_predictor(
    registry_path: Path = REGISTRY_PATH, models_dir: Path = MODELS_DIR
) -> Predictor | None:
    entry = active_entry(registry_path)
    if entry is None:
        return None
    model = joblib.load(models_dir / entry["filename"])
    return Predictor(
        model,
        version=entry["version"],
        feature_names=list(entry["features"]),
        model_version=entry["filename"],
    )


def features_for_matchup(
    history: list[GameRecord], season: int, game_date: date, home_id: int, away_id: int
) -> dict[str, float]:
    """Build features for a matchup from games strictly before ``game_date`` (leak-free)."""
    builder = FeatureBuilder()
    for game in sorted(history, key=lambda g: (g.season, g.game_date, g.game_id)):
        if game.game_date < game_date:
            builder.observe(game)
    return builder.features_for(season, game_date, home_id, away_id)
