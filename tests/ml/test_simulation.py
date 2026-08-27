"""Tests for the season simulation primitives."""

import copy
import math
import random
from datetime import date, timedelta
from typing import Any

import numpy as np

from ml.pipeline.features import FeatureBuilder
from ml.pipeline.inference import Predictor
from ml.pipeline.simulation import (
    ScheduledGame,
    expected_margin,
    make_scorer,
    sample_margin,
    simulate_regular_season,
)


def test_expected_margin_favours_the_stronger_home_team() -> None:
    # Equal ratings still favour home by the home-court bonus (100 Elo / 25 = 4 points).
    assert expected_margin(1500.0, 1500.0) == 4.0
    assert expected_margin(1600.0, 1500.0) > expected_margin(1500.0, 1600.0)


def test_sample_margin_sign_always_matches_the_winner() -> None:
    rng = random.Random(7)
    for _ in range(200):
        assert sample_margin(rng, 1500.0, 1700.0, home_won=True) > 0
        assert sample_margin(rng, 1700.0, 1500.0, home_won=False) < 0


def test_sample_margin_is_never_a_draw() -> None:
    rng = random.Random(11)
    margins = [sample_margin(rng, 1500.0, 1500.0, home_won=True) for _ in range(500)]
    assert all(m >= 1 for m in margins)


def test_sample_margin_is_deterministic_for_a_seed() -> None:
    a = [sample_margin(random.Random(3), 1550.0, 1500.0, home_won=True) for _ in range(5)]
    b = [sample_margin(random.Random(3), 1550.0, 1500.0, home_won=True) for _ in range(5)]
    assert a == b


def test_stronger_teams_win_by_more_on_average() -> None:
    rng = random.Random(19)
    blowout = [sample_margin(rng, 1800.0, 1400.0, home_won=True) for _ in range(2000)]
    close = [sample_margin(rng, 1500.0, 1500.0, home_won=True) for _ in range(2000)]
    assert sum(blowout) / len(blowout) > sum(close) / len(close)


class _FakeLogisticModel:
    """Mimics the sklearn LogisticRegression surface the fast path reads."""

    def __init__(self) -> None:
        self.coef_ = [[0.5, -0.25]]
        self.intercept_ = [0.1]

    def predict_proba(self, matrix: Any) -> Any:
        # Predictor slices the result as ``[:, 1]``, so this must be a numpy array.
        rows = []
        for row in matrix:
            z = 0.1 + 0.5 * float(row[0]) - 0.25 * float(row[1])
            p = 1.0 / (1.0 + math.exp(-z))
            rows.append([1.0 - p, p])
        return np.asarray(rows)


def test_make_scorer_fast_path_matches_predict_proba() -> None:
    predictor = Predictor(
        _FakeLogisticModel(),
        version=1,
        feature_names=["a", "b"],
        model_version="fake.pkl",
    )
    score = make_scorer(predictor)
    for features in ({"a": 1.0, "b": 2.0}, {"a": -3.0, "b": 0.5}, {"a": 0.0, "b": 0.0}):
        expected = predictor.predict_proba([features])[0]
        assert abs(score(features) - expected) < 1e-9


def test_scheduled_game_holds_the_matchup() -> None:
    game = ScheduledGame(
        game_id=1, season=2026, game_date=date(2026, 10, 20), home_team_id=2, visitor_team_id=3
    )
    assert game.home_team_id == 2
    assert game.visitor_team_id == 3


def _round_robin(team_ids: list[int], season: int = 2026) -> list[ScheduledGame]:
    """Home-and-away round robin, one game per day."""
    games: list[ScheduledGame] = []
    for home in team_ids:
        for away in team_ids:
            if home == away:
                continue
            games.append(
                ScheduledGame(
                    game_id=len(games) + 1,
                    season=season,
                    game_date=date(2026, 10, 20) + timedelta(days=len(games)),
                    home_team_id=home,
                    visitor_team_id=away,
                )
            )
    return games


def test_simulate_regular_season_gives_every_team_its_full_slate() -> None:
    schedule = _round_robin([1, 2, 3, 4])
    records = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.5, random.Random(5)
    )
    assert set(records) == {1, 2, 3, 4}
    for wins, losses in records.values():
        assert wins + losses == 6


def test_simulate_regular_season_certain_home_wins_produce_home_sweeps() -> None:
    schedule = [
        ScheduledGame(
            game_id=1, season=2026, game_date=date(2026, 10, 20), home_team_id=1, visitor_team_id=2
        ),
        ScheduledGame(
            game_id=2, season=2026, game_date=date(2026, 10, 22), home_team_id=1, visitor_team_id=2
        ),
    ]
    records = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 1.0, random.Random(1)
    )
    assert records[1] == [2, 0]
    assert records[2] == [0, 2]


def test_simulate_regular_season_is_deterministic_for_a_seed() -> None:
    schedule = _round_robin([1, 2, 3])
    first = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.6, random.Random(42)
    )
    second = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.6, random.Random(42)
    )
    assert first == second
