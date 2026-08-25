"""Process-wide holder for the active inference model.

Loaded once at startup and on explicit reload — never per request (docs/ml_lifecycle.md).
"""

from pathlib import Path

from ml.pipeline.inference import Predictor, load_active_predictor
from ml.pipeline.registry import MODELS_DIR, REGISTRY_PATH


class ActiveModel:
    def __init__(self) -> None:
        self._predictor: Predictor | None = None

    def load(self, registry_path: Path = REGISTRY_PATH, models_dir: Path = MODELS_DIR) -> None:
        self._predictor = load_active_predictor(registry_path, models_dir)

    def set_predictor(self, predictor: Predictor | None) -> None:
        self._predictor = predictor

    @property
    def predictor(self) -> Predictor | None:
        return self._predictor


active_model = ActiveModel()


def get_active_model() -> ActiveModel:
    return active_model
