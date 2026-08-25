"""Tests for the baseline and evaluation metrics."""

from ml.pipeline.baseline import baseline_probabilities, majority_class_probability
from ml.pipeline.evaluate import beats_baseline, evaluate


def test_majority_class_probability() -> None:
    assert majority_class_probability([1, 1, 1, 0]) == 0.75
    assert majority_class_probability([]) == 0.5
    assert baseline_probabilities(0.6, 3) == [0.6, 0.6, 0.6]


def test_evaluate_perfect_predictions() -> None:
    metrics = evaluate([1, 0, 1, 1], [0.9, 0.1, 0.8, 0.6])
    assert metrics["accuracy"] == 1.0
    assert metrics["log_loss"] >= 0.0
    assert 0.0 <= metrics["brier"] <= 1.0
    assert metrics["n"] == 4.0


def test_beats_baseline_requires_both_accuracy_and_log_loss() -> None:
    better = {"accuracy": 0.65, "log_loss": 0.60}
    base = {"accuracy": 0.58, "log_loss": 0.68}
    assert beats_baseline(better, base) is True

    worse_calibration = {"accuracy": 0.65, "log_loss": 0.70}
    assert beats_baseline(worse_calibration, base) is False
