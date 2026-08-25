"""Tests that a trained model learns signal and beats the baseline."""

from ml.pipeline.baseline import baseline_probabilities, majority_class_probability
from ml.pipeline.evaluate import beats_baseline, evaluate
from ml.pipeline.features import build_training_data
from ml.pipeline.train import predict_proba, train_model
from tests.ml.synth import synth_game_records


def test_model_beats_majority_baseline_on_synthetic_signal() -> None:
    features, labels, _ = build_training_data(synth_game_records())
    split = int(len(features) * 0.8)
    x_train, y_train = features[:split], labels[:split]
    x_eval, y_eval = features[split:], labels[split:]

    model = train_model(x_train, y_train)
    metrics = evaluate(y_eval, predict_proba(model, x_eval))

    base_prob = majority_class_probability(y_train)
    base_metrics = evaluate(y_eval, baseline_probabilities(base_prob, len(y_eval)))

    assert beats_baseline(metrics, base_metrics) is True


def test_predict_proba_returns_probabilities() -> None:
    features, labels, _ = build_training_data(synth_game_records())
    model = train_model(features, labels)
    probs = predict_proba(model, features[:5])
    assert len(probs) == 5
    assert all(0.0 <= p <= 1.0 for p in probs)
