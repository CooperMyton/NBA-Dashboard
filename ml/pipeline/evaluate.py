"""Evaluation metrics: accuracy, log loss, and calibration (Brier score).

Logged for every training run — win or lose — so rejected candidates are recorded too
(docs/ml_lifecycle.md).
"""

from sklearn.metrics import accuracy_score, brier_score_loss, log_loss


def evaluate(y_true: list[int], y_prob: list[float]) -> dict[str, float]:
    y_pred = [1 if p >= 0.5 else 0 for p in y_prob]
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "n": float(len(y_true)),
    }


def beats_baseline(model_metrics: dict[str, float], baseline_metrics: dict[str, float]) -> bool:
    """A candidate must be at least as accurate AND at least as well-calibrated (log loss)."""
    return (
        model_metrics["accuracy"] >= baseline_metrics["accuracy"]
        and model_metrics["log_loss"] <= baseline_metrics["log_loss"]
    )
