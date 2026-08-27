"""Monte Carlo simulation primitives for projecting a season.

The simulation drives the same ``FeatureBuilder`` used for training, so simulated games are
scored exactly as real ones were. Only the *margin* of a game feeds the features (see
``features.py`` — no feature reads raw points), so a simulated game needs a plausible margin,
not a plausible box score.
"""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ml.pipeline.features import FeatureBuilder, GameRecord
from ml.pipeline.inference import Predictor

# Points of margin per Elo point of rating difference. 25 is the conventional NBA figure: a
# 100-Elo edge is worth roughly 4 points, which matches the home-court bonus in features.py.
_ELO_POINTS_DIVISOR = 25.0
_ELO_HOME_ADV = 100.0

# Standard deviation of an NBA game margin. Used to spread simulated margins around the
# Elo-implied expectation so form and net-rating features see realistic variation.
_MARGIN_SD = 12.0


@dataclass(frozen=True)
class ScheduledGame:
    """An unplayed game to be simulated."""

    game_id: int
    season: int
    game_date: date
    home_team_id: int
    visitor_team_id: int


def expected_margin(home_elo: float, away_elo: float) -> float:
    """Elo-implied expected home margin, in points, including home-court advantage."""
    return (home_elo - away_elo + _ELO_HOME_ADV) / _ELO_POINTS_DIVISOR


def sample_margin(rng: random.Random, home_elo: float, away_elo: float, *, home_won: bool) -> int:
    """Sample a home margin consistent with an already-decided winner.

    The winner is drawn from the model's probability; the margin is drawn around the
    Elo-implied expectation and reflected if its sign disagrees, so stronger teams win by more
    without altering the model's win probability. Never returns 0 — basketball has no draws.
    """
    margin = rng.gauss(expected_margin(home_elo, away_elo), _MARGIN_SD)
    if (margin > 0) != home_won:
        margin = -margin
    magnitude = max(1, int(round(abs(margin))))
    return magnitude if home_won else -magnitude


def make_scorer(predictor: Predictor) -> Callable[[dict[str, float]], float]:
    """Return a fast P(home win) function for ``predictor``.

    A simulation run evaluates millions of games, where ``predict_proba``'s per-call array
    overhead dominates. Logistic regression is just ``sigmoid(w·x + b)``, so read the fitted
    coefficients once and compute it directly. Anything else falls back to ``predict_proba``.
    """
    model: Any = predictor._model
    names = list(predictor.feature_names)
    coef = getattr(model, "coef_", None)
    intercept = getattr(model, "intercept_", None)

    if coef is None or intercept is None:

        def score_via_model(features: dict[str, float]) -> float:
            return predictor.predict_proba([features])[0]

        return score_via_model

    weights = [float(w) for w in coef[0]]
    bias = float(intercept[0])

    def score_fast(features: dict[str, float]) -> float:
        total = bias
        for name, weight in zip(names, weights, strict=True):
            total += weight * features[name]
        return 1.0 / (1.0 + math.exp(-total))

    return score_fast


def simulate_regular_season(
    builder: FeatureBuilder,
    schedule: list[ScheduledGame],
    score: Callable[[dict[str, float]], float],
    rng: random.Random,
) -> dict[int, list[int]]:
    """Simulate one regular season, returning ``{team_id: [wins, losses]}``.

    ``builder`` is mutated as games resolve, so callers must pass a fresh copy per run. Games are
    played in schedule order; each simulated result is observed so Elo and rolling form evolve
    exactly as they would during a real season.
    """
    records: dict[int, list[int]] = {}
    for game in schedule:
        records.setdefault(game.home_team_id, [0, 0])
        records.setdefault(game.visitor_team_id, [0, 0])

    for game in sorted(schedule, key=lambda g: (g.game_date, g.game_id)):
        features = builder.features_for(
            game.season, game.game_date, game.home_team_id, game.visitor_team_id
        )
        home_won = rng.random() < score(features)
        margin = sample_margin(rng, features["home_elo"], features["away_elo"], home_won=home_won)
        # Only the score *difference* reaches the features, so a nominal base is sufficient.
        builder.observe(
            GameRecord(
                game_id=game.game_id,
                season=game.season,
                game_date=game.game_date,
                home_team_id=game.home_team_id,
                visitor_team_id=game.visitor_team_id,
                home_score=100 + margin,
                visitor_score=100,
            )
        )
        winner, loser = (
            (game.home_team_id, game.visitor_team_id)
            if home_won
            else (game.visitor_team_id, game.home_team_id)
        )
        records[winner][0] += 1
        records[loser][1] += 1

    return records
