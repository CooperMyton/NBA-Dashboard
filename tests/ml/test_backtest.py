"""Tests for the projection backtest scoring."""

import pytest

from ml.pipeline.backtest import evaluate_projection


def test_mae_is_the_mean_absolute_win_error() -> None:
    result = evaluate_projection({1: 50.0, 2: 30.0}, {1: 54, 2: 28})
    assert result.teams == 2
    assert result.mae == pytest.approx((4 + 2) / 2)


def test_mean_baseline_predicts_the_league_average_for_everyone() -> None:
    # Actual wins 60 and 20 average to 40, so the no-skill forecast misses each by 20.
    result = evaluate_projection({1: 60.0, 2: 20.0}, {1: 60, 2: 20})
    assert result.mae == 0.0
    assert result.mae_mean_baseline == pytest.approx(20.0)


def test_persistence_baseline_carries_last_season_forward() -> None:
    result = evaluate_projection({1: 45.0, 2: 45.0}, {1: 50, 2: 40}, {1: 44, 2: 46})
    assert result.mae_persistence_baseline == pytest.approx((6 + 6) / 2)


def test_persistence_baseline_skips_teams_with_no_prior_season() -> None:
    result = evaluate_projection({1: 45.0, 2: 45.0}, {1: 50, 2: 40}, {1: 44})
    # Only team 1 has a prior season, so persistence is scored on it alone.
    assert result.mae_persistence_baseline == pytest.approx(6.0)
    assert result.rows[1].previous is None


def test_persistence_baseline_is_none_when_nobody_has_a_prior_season() -> None:
    result = evaluate_projection({1: 45.0}, {1: 50})
    assert result.mae_persistence_baseline is None


def test_only_teams_present_on_both_sides_are_scored() -> None:
    result = evaluate_projection({1: 50.0, 2: 30.0, 3: 41.0}, {1: 54, 2: 28, 9: 41})
    assert [r.team_id for r in result.rows] == [1, 2]


def test_no_overlapping_teams_is_an_error() -> None:
    with pytest.raises(ValueError):
        evaluate_projection({1: 50.0}, {2: 50})


def test_season_and_simulations_are_carried_through() -> None:
    result = evaluate_projection({1: 41.0}, {1: 41}, season=2024, simulations=300)
    assert result.season == 2024
    assert result.simulations == 300
