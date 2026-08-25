"""Model training: standardized logistic regression over the engineered features.

CPU-only and pickle-serializable — keeps the $0 budget and simple inference (docs/ml_lifecycle.md).
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.pipeline.features import FEATURE_NAMES

# Candidate algorithms trained and compared each run; the best beats-baseline model is promoted.
ALGORITHMS = ["logistic_regression", "gradient_boosting"]


def to_matrix(
    rows: list[dict[str, float]], feature_names: list[str] = FEATURE_NAMES
) -> NDArray[np.float64]:
    return np.array([[row[name] for name in feature_names] for row in rows], dtype=float)


def train_model(rows: list[dict[str, float]], labels: list[int]) -> Pipeline:
    """Train the default (logistic regression) model — kept for back-compat."""
    return train_logistic_regression(rows, labels)


def train_logistic_regression(rows: list[dict[str, float]], labels: list[int]) -> Pipeline:
    model = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))])
    model.fit(to_matrix(rows), labels)
    return model


def train_gradient_boosting(rows: list[dict[str, float]], labels: list[int]) -> Pipeline:
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                HistGradientBoostingClassifier(
                    max_iter=300, learning_rate=0.06, max_depth=3, l2_regularization=1.0
                ),
            ),
        ]
    )
    model.fit(to_matrix(rows), labels)
    return model


def train_by_name(name: str, rows: list[dict[str, float]], labels: list[int]) -> Pipeline:
    if name == "logistic_regression":
        return train_logistic_regression(rows, labels)
    if name == "gradient_boosting":
        return train_gradient_boosting(rows, labels)
    raise ValueError(f"Unknown algorithm: {name}")


def predict_proba(model: Any, rows: list[dict[str, float]]) -> list[float]:
    probabilities = model.predict_proba(to_matrix(rows))[:, 1]
    return [float(p) for p in probabilities]
