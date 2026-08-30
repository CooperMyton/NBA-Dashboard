"""Tests for player name normalisation and matching."""

from etl.core.names import match_players, normalize_name


def test_normalize_strips_case_punctuation_and_accents() -> None:
    assert normalize_name("A.J. Lawson") == "aj lawson"
    assert normalize_name("Luka Dončić") == "luka doncic"
    assert normalize_name("Jaren Jackson Jr.") == "jaren jackson"
    assert normalize_name("Nigel Hayes-Davis") == "nigel hayes davis"


def test_match_players_pairs_on_exact_normalized_name() -> None:
    nba = [(1, "Luka Doncic", "LAL")]
    db = [(50, "Luka Dončić", "LAL")]
    matched, unmatched = match_players(nba, db)
    assert matched == {1: 50}
    assert unmatched == []


def test_match_players_second_pass_resolves_nicknames_by_last_name_and_team() -> None:
    nba = [(2, "Nic Claxton", "BKN"), (3, "Alex Sarr", "WAS")]
    db = [(60, "Nicolas Claxton", "BKN"), (61, "Alexandre Sarr", "WAS")]
    matched, unmatched = match_players(nba, db)
    assert matched == {2: 60, 3: 61}
    assert unmatched == []


def test_match_players_does_not_pair_same_last_name_on_different_teams() -> None:
    nba = [(4, "Bones Hyland", "MIN")]
    db = [(70, "Nah'Shon Hyland", "LAC")]
    matched, unmatched = match_players(nba, db)
    assert matched == {}
    assert unmatched == [4]


def test_match_players_second_pass_skips_ambiguous_last_names() -> None:
    # Two players share a last name on one team: the pairing is not decidable.
    nba = [(5, "Bub Carrington", "WAS")]
    db = [(80, "Carlton Carrington", "WAS"), (81, "Other Carrington", "WAS")]
    matched, unmatched = match_players(nba, db)
    assert matched == {}
    assert unmatched == [5]


def test_match_players_reports_unmatched() -> None:
    nba = [(6, "Yang Hansen", "POR")]
    matched, unmatched = match_players(nba, [])
    assert matched == {}
    assert unmatched == [6]


def test_match_players_never_assigns_one_db_player_twice() -> None:
    nba = [(7, "Nic Claxton", "BKN"), (8, "Nicolas Claxton", "BKN")]
    db = [(90, "Nicolas Claxton", "BKN")]
    matched, unmatched = match_players(nba, db)
    assert list(matched.values()) == [90]
    assert len(unmatched) == 1
