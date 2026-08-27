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


# The higher seed hosts games 1, 2, 5 and 7 (the NBA's 2-2-1-1-1 pattern).
_HOME_GAMES_FOR_HIGHER_SEED = (1, 2, 5, 7)


@dataclass
class SeasonOutcome:
    """The result of one simulated season."""

    records: dict[int, list[int]]
    seeds: dict[int, int]
    playoff_teams: set[int]
    conference_champions: set[int]
    champion: int


def seed_conference(
    records: dict[int, list[int]], team_ids: list[int], rng: random.Random
) -> list[int]:
    """Order a conference's teams best-to-worst, breaking ties randomly.

    Real NBA tiebreakers (head-to-head, division, conference record) are not modelled; a random
    break reflects the genuine uncertainty rather than inventing precision.
    """
    shuffled = list(team_ids)
    rng.shuffle(shuffled)
    return sorted(shuffled, key=lambda t: records.get(t, [0, 0])[0], reverse=True)


def simulate_series(
    score_home: Callable[[int, int], float], higher: int, lower: int, rng: random.Random
) -> int:
    """Simulate a best-of-7 series and return the winning team id."""
    wins = {higher: 0, lower: 0}
    game = 1
    while wins[higher] < 4 and wins[lower] < 4:
        if game in _HOME_GAMES_FOR_HIGHER_SEED:
            home, away = higher, lower
        else:
            home, away = lower, higher
        winner = home if rng.random() < score_home(home, away) else away
        wins[winner] += 1
        game += 1
    return higher if wins[higher] == 4 else lower


def resolve_play_in(
    seeds: list[int], score_home: Callable[[int, int], float], rng: random.Random
) -> list[int]:
    """Return the eight playoff teams for a conference, in seed order.

    Seeds 1-6 qualify directly. Of 7-10: the 7v8 winner takes the 7 seed, the 9v10 loser is out,
    and the 7v8 loser hosts the 9v10 winner for the 8 seed.
    """
    direct = seeds[:6]
    seven, eight, nine, ten = seeds[6], seeds[7], seeds[8], seeds[9]

    seven_eight_winner = seven if rng.random() < score_home(seven, eight) else eight
    seven_eight_loser = eight if seven_eight_winner == seven else seven

    nine_ten_winner = nine if rng.random() < score_home(nine, ten) else ten

    final_home = seven_eight_loser
    final_winner = (
        final_home if rng.random() < score_home(final_home, nine_ten_winner) else nine_ten_winner
    )
    return [*direct, seven_eight_winner, final_winner]


def simulate_season(
    builder: FeatureBuilder,
    schedule: list[ScheduledGame],
    score: Callable[[dict[str, float]], float],
    rng: random.Random,
    conferences: dict[int, str],
) -> SeasonOutcome:
    """Simulate a full regular season plus postseason."""
    records = simulate_regular_season(builder, schedule, score, rng)

    # Postseason games are scored from end-of-season team state. Rest-day features are
    # approximate here; a fixed post-season date keeps every series on the same footing.
    playoff_date = max(g.game_date for g in schedule)
    season = schedule[0].season

    def score_home(home_id: int, away_id: int) -> float:
        return score(builder.features_for(season, playoff_date, home_id, away_id))

    seeds: dict[int, int] = {}
    playoff_teams: set[int] = set()
    finalists: list[int] = []

    for conference in sorted({conferences[t] for t in records}):
        members = [t for t in records if conferences[t] == conference]
        order = seed_conference(records, members, rng)
        for index, team_id in enumerate(order, start=1):
            seeds[team_id] = index

        qualified = resolve_play_in(order, score_home, rng)
        playoff_teams.update(qualified)

        round_teams = list(qualified)
        while len(round_teams) > 1:
            next_round = []
            for i in range(len(round_teams) // 2):
                # Bracket position pairs 1v8, 2v7, ... but after round one the survivor of a
                # pairing may be the lower seed, so home court is decided by actual seed.
                first = round_teams[i]
                second = round_teams[len(round_teams) - 1 - i]
                higher, lower = (
                    (first, second) if seeds[first] <= seeds[second] else (second, first)
                )
                next_round.append(simulate_series(score_home, higher, lower, rng))
            round_teams = next_round
        finalists.append(round_teams[0])

    # Finals home court goes to the better regular-season record, not to a conference.
    first_finalist, second_finalist = finalists
    if records[second_finalist][0] > records[first_finalist][0]:
        first_finalist, second_finalist = second_finalist, first_finalist
    champion = simulate_series(score_home, first_finalist, second_finalist, rng)

    return SeasonOutcome(
        records=records,
        seeds=seeds,
        playoff_teams=playoff_teams,
        conference_champions=set(finalists),
        champion=champion,
    )
