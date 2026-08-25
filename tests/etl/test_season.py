"""Tests for the NBA season helper."""

from datetime import date

from etl.core.season import current_nba_season


def test_current_nba_season_boundaries() -> None:
    assert current_nba_season(date(2024, 11, 1)) == 2024  # mid-season
    assert current_nba_season(date(2025, 3, 15)) == 2024  # spring = same season
    assert current_nba_season(date(2024, 10, 1)) == 2024  # season opens in October
    assert current_nba_season(date(2024, 9, 30)) == 2023  # offseason = prior season
    assert current_nba_season(date(2025, 8, 1)) == 2024  # summer = prior season
