"""Feature engineering for the home-win model.

Features for a game are computed from only the games that occurred *before* it (no leakage):
a chronological ``FeatureBuilder`` accumulates per-team state and is queried before each game is
observed. State resets per season. All features derive from free ``games`` data (D-002/D-006).
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date

FEATURE_NAMES = [
    "home_form_win_pct",
    "away_form_win_pct",
    "home_form_pt_diff",
    "away_form_pt_diff",
    "home_rest_days",
    "away_rest_days",
    "home_net_rating",
    "away_net_rating",
    "h2h_home_win_pct",
    "home_elo",
    "away_elo",
    "elo_win_prob",
]

_FORM_WINDOW = 10
_DEFAULT_WIN_PCT = 0.5
_DEFAULT_PT_DIFF = 0.0
_DEFAULT_REST_DAYS = 3.0
_DEFAULT_NET_RATING = 0.0
_DEFAULT_H2H = 0.5

# Elo ratings: standard chess-style rating adapted for basketball, with a home-court bonus.
# Unlike the per-season stats, Elo carries across seasons (regressed toward the mean each
# offseason) so team strength informs predictions from a new season's first game onward.
_ELO_DEFAULT = 1500.0
_ELO_K = 20.0
_ELO_HOME_ADV = 100.0
_ELO_SEASON_CARRY = 0.75


def _elo_default() -> float:
    return _ELO_DEFAULT


def _elo_expected_home(home_elo: float, away_elo: float) -> float:
    """Elo-implied probability the home team wins (includes the home-court bonus)."""
    return float(1.0 / (1.0 + 10.0 ** ((away_elo - home_elo - _ELO_HOME_ADV) / 400.0)))


@dataclass(frozen=True)
class GameRecord:
    game_id: int
    season: int
    game_date: date
    home_team_id: int
    visitor_team_id: int
    home_score: int
    visitor_score: int

    @property
    def home_won(self) -> int:
        return 1 if self.home_score > self.visitor_score else 0


def _new_form() -> deque[tuple[bool, float]]:
    return deque(maxlen=_FORM_WINDOW)


def _new_h2h() -> dict[int, int]:
    return defaultdict(int)


def _win_pct(form: deque[tuple[bool, float]]) -> float:
    if not form:
        return _DEFAULT_WIN_PCT
    return sum(1 for won, _ in form if won) / len(form)


def _avg_pt_diff(form: deque[tuple[bool, float]]) -> float:
    if not form:
        return _DEFAULT_PT_DIFF
    return sum(pt for _, pt in form) / len(form)


class FeatureBuilder:
    """Accumulates per-team season state to produce leak-free features."""

    def __init__(self) -> None:
        self._season: int | None = None
        self._form: dict[int, deque[tuple[bool, float]]] = defaultdict(_new_form)
        self._games_played: dict[int, int] = defaultdict(int)
        self._pt_diff_sum: dict[int, float] = defaultdict(float)
        self._last_date: dict[int, date] = {}
        # h2h[(low_id, high_id)][team_id] = wins by that team in the matchup
        self._h2h: dict[tuple[int, int], dict[int, int]] = defaultdict(_new_h2h)
        self._elo: dict[int, float] = defaultdict(_elo_default)

    def _reset(self, season: int) -> None:
        self._season = season
        self._form.clear()
        self._games_played.clear()
        self._pt_diff_sum.clear()
        self._last_date.clear()
        self._h2h.clear()
        # Elo carries over, regressed toward the mean (offseason reversion).
        for team_id in list(self._elo):
            self._elo[team_id] = _ELO_DEFAULT + _ELO_SEASON_CARRY * (
                self._elo[team_id] - _ELO_DEFAULT
            )

    def _net_rating(self, team_id: int) -> float:
        played = self._games_played[team_id]
        return self._pt_diff_sum[team_id] / played if played else _DEFAULT_NET_RATING

    def _rest_days(self, team_id: int, game_date: date) -> float:
        last = self._last_date.get(team_id)
        return float((game_date - last).days) if last is not None else _DEFAULT_REST_DAYS

    def _h2h_home_win_pct(self, home_id: int, away_id: int) -> float:
        key = (min(home_id, away_id), max(home_id, away_id))
        record = self._h2h.get(key)
        if not record:
            return _DEFAULT_H2H
        total = record.get(home_id, 0) + record.get(away_id, 0)
        return record.get(home_id, 0) / total if total else _DEFAULT_H2H

    def features_for(
        self, season: int, game_date: date, home_id: int, away_id: int
    ) -> dict[str, float]:
        if season != self._season:
            # First game of a season: per-season stats reset, but Elo carries over.
            home_elo = self._elo[home_id]
            away_elo = self._elo[away_id]
            return {
                "home_form_win_pct": _DEFAULT_WIN_PCT,
                "away_form_win_pct": _DEFAULT_WIN_PCT,
                "home_form_pt_diff": _DEFAULT_PT_DIFF,
                "away_form_pt_diff": _DEFAULT_PT_DIFF,
                "home_rest_days": _DEFAULT_REST_DAYS,
                "away_rest_days": _DEFAULT_REST_DAYS,
                "home_net_rating": _DEFAULT_NET_RATING,
                "away_net_rating": _DEFAULT_NET_RATING,
                "h2h_home_win_pct": _DEFAULT_H2H,
                "home_elo": home_elo,
                "away_elo": away_elo,
                "elo_win_prob": _elo_expected_home(home_elo, away_elo),
            }
        home_elo = self._elo[home_id]
        away_elo = self._elo[away_id]
        return {
            "home_form_win_pct": _win_pct(self._form[home_id]),
            "away_form_win_pct": _win_pct(self._form[away_id]),
            "home_form_pt_diff": _avg_pt_diff(self._form[home_id]),
            "away_form_pt_diff": _avg_pt_diff(self._form[away_id]),
            "home_rest_days": self._rest_days(home_id, game_date),
            "away_rest_days": self._rest_days(away_id, game_date),
            "home_net_rating": self._net_rating(home_id),
            "away_net_rating": self._net_rating(away_id),
            "h2h_home_win_pct": self._h2h_home_win_pct(home_id, away_id),
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_win_prob": _elo_expected_home(home_elo, away_elo),
        }

    def observe(self, game: GameRecord) -> None:
        if game.season != self._season:
            self._reset(game.season)

        home, away = game.home_team_id, game.visitor_team_id
        home_diff = float(game.home_score - game.visitor_score)
        home_won = bool(game.home_won)

        self._form[home].append((home_won, home_diff))
        self._form[away].append((not home_won, -home_diff))
        self._games_played[home] += 1
        self._games_played[away] += 1
        self._pt_diff_sum[home] += home_diff
        self._pt_diff_sum[away] += -home_diff
        self._last_date[home] = game.game_date
        self._last_date[away] = game.game_date

        key = (min(home, away), max(home, away))
        winner = home if home_won else away
        self._h2h[key][winner] += 1

        # Update Elo ratings from the result (zero-sum between the two teams).
        expected_home = _elo_expected_home(self._elo[home], self._elo[away])
        delta = _ELO_K * (float(home_won) - expected_home)
        self._elo[home] += delta
        self._elo[away] -= delta


def build_training_data(
    games: list[GameRecord],
) -> tuple[list[dict[str, float]], list[int], list[int]]:
    """Return (feature rows, labels, game_ids) in chronological order."""
    ordered = sorted(games, key=lambda g: (g.season, g.game_date, g.game_id))
    builder = FeatureBuilder()
    features: list[dict[str, float]] = []
    labels: list[int] = []
    game_ids: list[int] = []
    for game in ordered:
        features.append(
            builder.features_for(
                game.season, game.game_date, game.home_team_id, game.visitor_team_id
            )
        )
        labels.append(game.home_won)
        game_ids.append(game.game_id)
        builder.observe(game)
    return features, labels, game_ids
