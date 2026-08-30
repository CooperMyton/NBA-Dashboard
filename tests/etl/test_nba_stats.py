"""Tests for nba_api payload parsing."""

from etl.providers.nba_stats import parse_experience, rows_to_stat_lines


def test_parse_experience_maps_rookie_to_zero() -> None:
    assert parse_experience("R") == 0


def test_parse_experience_reads_year_counts() -> None:
    assert parse_experience("7") == 7


def test_parse_experience_defaults_unknown_to_zero() -> None:
    assert parse_experience("") == 0
    assert parse_experience("unknown") == 0


def test_rows_to_stat_lines_joins_base_and_advanced_on_player_id() -> None:
    base = [
        {
            "PLAYER_ID": 1,
            "PLAYER_NAME": "AJ Green",
            "TEAM_ABBREVIATION": "MIL",
            "GP": 78,
            "MIN": 29.1,
            "PTS": 10.4,
            "REB": 2.7,
            "AST": 1.9,
            "FG3_PCT": 0.419,
            "FG3A": 7.1,
        }
    ]
    advanced = [{"PLAYER_ID": 1, "TS_PCT": 0.627, "USG_PCT": 0.135}]
    lines = rows_to_stat_lines(base, advanced, season=2025)
    assert len(lines) == 1
    assert lines[0].nba_player_id == 1
    assert lines[0].season == 2025
    assert lines[0].ts_pct == 0.627
    assert lines[0].usage_pct == 0.135


def test_rows_to_stat_lines_skips_players_missing_advanced_rows() -> None:
    base = [
        {
            "PLAYER_ID": 2,
            "PLAYER_NAME": "Ghost",
            "TEAM_ABBREVIATION": "TOR",
            "GP": 1,
            "MIN": 1.0,
            "PTS": 0.0,
            "REB": 0.0,
            "AST": 0.0,
            "FG3_PCT": 0.0,
            "FG3A": 0.0,
        }
    ]
    assert rows_to_stat_lines(base, [], season=2025) == []


def test_rows_to_stat_lines_treats_null_percentages_as_zero() -> None:
    base = [
        {
            "PLAYER_ID": 3,
            "PLAYER_NAME": "No Threes",
            "TEAM_ABBREVIATION": "DEN",
            "GP": 40,
            "MIN": 12.0,
            "PTS": 4.0,
            "REB": 3.0,
            "AST": 0.5,
            "FG3_PCT": None,
            "FG3A": 0.0,
        }
    ]
    advanced = [{"PLAYER_ID": 3, "TS_PCT": 0.55, "USG_PCT": 0.14}]
    lines = rows_to_stat_lines(base, advanced, season=2025)
    assert lines[0].fg3_pct == 0.0
