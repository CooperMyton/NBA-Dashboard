"""Majority-class baseline: always predict the home team wins.

A trained model must beat this on both accuracy and log loss before it may be registered
(spec / docs/decisions.md D-003).
"""


def majority_class_probability(labels: list[int]) -> float:
    """Base rate of home wins in the training labels (the constant baseline probability)."""
    if not labels:
        return 0.5
    return sum(labels) / len(labels)


def baseline_probabilities(probability: float, n: int) -> list[float]:
    return [probability] * n
