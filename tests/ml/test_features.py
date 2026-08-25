"""Tests for leak-free feature engineering."""

from datetime import date

from ml.pipeline.features import FEATURE_NAMES, GameRecord, build_training_data


def _game(gid: int, day: int, home: int, away: int, hs: int, vs: int) -> GameRecord:
    return GameRecord(
        game_id=gid,
        season=2023,
        game_date=date(2024, 1, day),
        home_team_id=home,
        visitor_team_id=away,
        home_score=hs,
        visitor_score=vs,
    )


def test_first_game_of_season_uses_defaults() -> None:
    games = [_game(1, 1, home=10, away=20, hs=100, vs=90)]
    features, labels, ids = build_training_data(games)

    assert labels == [1]
    assert ids == [1]
    assert set(features[0]) == set(FEATURE_NAMES)
    assert features[0]["home_form_win_pct"] == 0.5
    assert features[0]["home_rest_days"] == 3.0
    assert features[0]["h2h_home_win_pct"] == 0.5


def test_second_game_reflects_prior_history_without_leakage() -> None:
    games = [
        _game(1, 1, home=10, away=20, hs=100, vs=90),  # team 10 beats team 20 by 10
        _game(2, 2, home=20, away=10, hs=100, vs=90),  # rematch next day, team 20 hosts
    ]
    features, labels, _ = build_training_data(games)
    row = features[1]  # features for game 2, computed from game 1 only

    # Home is team 20 (lost game 1); away is team 10 (won game 1).
    assert row["home_form_win_pct"] == 0.0
    assert row["away_form_win_pct"] == 1.0
    assert row["home_form_pt_diff"] == -10.0
    assert row["away_form_pt_diff"] == 10.0
    assert row["home_rest_days"] == 1.0
    assert row["away_rest_days"] == 1.0
    assert row["home_net_rating"] == -10.0
    assert row["away_net_rating"] == 10.0
    # Head-to-head so far: team 10 leads 1-0, so the current home team (20) has 0% h2h.
    assert row["h2h_home_win_pct"] == 0.0
    assert labels == [1, 1]


def test_season_change_resets_state() -> None:
    games = [
        GameRecord(1, 2022, date(2023, 1, 1), 10, 20, 100, 90),
        GameRecord(2, 2023, date(2024, 1, 1), 10, 20, 80, 100),
    ]
    features, _, _ = build_training_data(games)
    # First game of 2023 must not see 2022 state.
    assert features[1]["home_form_win_pct"] == 0.5
    assert features[1]["home_net_rating"] == 0.0
