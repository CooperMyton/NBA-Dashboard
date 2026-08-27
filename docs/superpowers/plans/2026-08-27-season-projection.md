# Season Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project 2026-27 records, standings, and playoff odds by Monte Carlo simulating the loaded schedule with the active win-probability model.

**Architecture:** A pure simulation module in `ml/pipeline/simulation.py` drives the existing `FeatureBuilder` so simulated games are scored exactly as trained. An ETL job runs it N times, aggregates per-team rates, and upserts them into a new `season_projections` table. A read-only API endpoint serves them to a new React page.

**Tech Stack:** Python 3.12 (uv), SQLAlchemy 2.0 async, Alembic, FastAPI, pytest; React 18 + TypeScript + TanStack Query + Vite.

## Global Constraints

- Line length 100. `ruff check .`, `black --check .`, and `mypy backend etl ml` must all pass clean.
- `mypy` runs in strict mode. Annotate every function signature, including tests.
- Backend coverage gate: `pytest --cov=backend --cov-fail-under=80`.
- All datetimes UTC (`datetime.now(UTC)`).
- Business logic lives in services/jobs; routers stay thin.
- Migrations are the only schema path, and downgrades are tested.
- Frontend: no ad-hoc `fetch` in components — data comes from typed hooks in `src/hooks`.
- Frontend gates: `npm run lint && npm run typecheck && npm run test && npm run build`.
- Simulation must be deterministic given a seed — pass `random.Random` explicitly, never use module-level `random`.

---

### Task 1: Simulation primitives — margin sampling and a fast scorer

**Files:**
- Create: `ml/pipeline/simulation.py`
- Test: `tests/ml/test_simulation.py`

**Interfaces:**
- Consumes: `ml.pipeline.features.FeatureBuilder`, `GameRecord`, `FEATURE_NAMES`; `ml.pipeline.inference.Predictor`
- Produces:
  - `ScheduledGame` dataclass: `game_id: int, season: int, game_date: date, home_team_id: int, visitor_team_id: int`
  - `expected_margin(home_elo: float, away_elo: float) -> float`
  - `sample_margin(rng: random.Random, home_elo: float, away_elo: float, home_won: bool) -> int`
  - `make_scorer(predictor: Predictor) -> Callable[[dict[str, float]], float]`

**Why a fast scorer:** the job evaluates ~2.4M games (2,000 sims x 1,200). `sklearn`'s `predict_proba` costs ~50-100 us per call from array wrapping alone, which would dominate runtime. For a `LogisticRegression` the probability is exactly `sigmoid(w·x + b)`, so we read `coef_`/`intercept_` once and compute it directly. Any other estimator falls back to `predict_proba`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the season simulation primitives."""

import math
import random

from ml.pipeline.simulation import (
    ScheduledGame,
    expected_margin,
    make_scorer,
    sample_margin,
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

    def predict_proba(self, matrix: list[list[float]]) -> list[list[float]]:
        rows = []
        for row in matrix:
            z = 0.1 + 0.5 * row[0] - 0.25 * row[1]
            p = 1.0 / (1.0 + math.exp(-z))
            rows.append([1.0 - p, p])
        return rows


def test_make_scorer_fast_path_matches_predict_proba() -> None:
    from ml.pipeline.inference import Predictor

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
    from datetime import date

    game = ScheduledGame(
        game_id=1, season=2026, game_date=date(2026, 10, 20), home_team_id=2, visitor_team_id=3
    )
    assert game.home_team_id == 2
    assert game.visitor_team_id == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings`
Expected: FAIL — `ModuleNotFoundError: No module named 'ml.pipeline.simulation'`

- [ ] **Step 3: Implement the module**

```python
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


def sample_margin(
    rng: random.Random, home_elo: float, away_elo: float, *, home_won: bool
) -> int:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings`
Expected: PASS (7 tests)

- [ ] **Step 5: Lint, type-check, commit**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy ml
git add ml/pipeline/simulation.py tests/ml/test_simulation.py
git commit -m "Add season simulation primitives: margin sampling and fast scorer"
```

---

### Task 2: Regular-season simulation

**Files:**
- Modify: `ml/pipeline/simulation.py`
- Test: `tests/ml/test_simulation.py`

**Interfaces:**
- Consumes: Task 1's `ScheduledGame`, `sample_margin`, `make_scorer`
- Produces: `simulate_regular_season(builder: FeatureBuilder, schedule: list[ScheduledGame], score: Callable[[dict[str, float]], float], rng: random.Random) -> dict[int, list[int]]` returning `{team_id: [wins, losses]}`. The caller passes a **fresh deep copy** of `builder` per run.

- [ ] **Step 1: Write the failing tests**

```python
def test_simulate_regular_season_gives_every_team_its_full_slate() -> None:
    import copy
    from datetime import date, timedelta

    from ml.pipeline.features import FeatureBuilder
    from ml.pipeline.simulation import simulate_regular_season

    start = date(2026, 10, 20)
    schedule = []
    gid = 0
    # Four teams, home-and-away round robin = 6 games per team.
    for home in range(1, 5):
        for away in range(1, 5):
            if home == away:
                continue
            gid += 1
            schedule.append(
                ScheduledGame(
                    game_id=gid,
                    season=2026,
                    game_date=start + timedelta(days=gid),
                    home_team_id=home,
                    visitor_team_id=away,
                )
            )

    records = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.5, random.Random(5)
    )
    assert set(records) == {1, 2, 3, 4}
    for wins, losses in records.values():
        assert wins + losses == 6


def test_simulate_regular_season_certain_home_wins_produce_home_sweeps() -> None:
    import copy
    from datetime import date

    from ml.pipeline.features import FeatureBuilder
    from ml.pipeline.simulation import simulate_regular_season

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
    import copy
    from datetime import date, timedelta

    from ml.pipeline.features import FeatureBuilder
    from ml.pipeline.simulation import simulate_regular_season

    schedule = [
        ScheduledGame(
            game_id=i,
            season=2026,
            game_date=date(2026, 10, 20) + timedelta(days=i),
            home_team_id=1 + (i % 2),
            visitor_team_id=2 - (i % 2),
        )
        for i in range(1, 21)
    ]
    first = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.6, random.Random(42)
    )
    second = simulate_regular_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.6, random.Random(42)
    )
    assert first == second
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings -k regular_season`
Expected: FAIL — `ImportError: cannot import name 'simulate_regular_season'`

- [ ] **Step 3: Implement**

Append to `ml/pipeline/simulation.py` (and add `from ml.pipeline.features import FeatureBuilder, GameRecord` to the imports):

```python
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
        margin = sample_margin(
            rng, features["home_elo"], features["away_elo"], home_won=home_won
        )
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings`
Expected: PASS (10 tests)

- [ ] **Step 5: Lint, type-check, commit**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy ml
git add ml/pipeline/simulation.py tests/ml/test_simulation.py
git commit -m "Simulate a regular season with evolving team state"
```

---

### Task 3: Play-in, bracket, and a full season run

**Files:**
- Modify: `ml/pipeline/simulation.py`
- Test: `tests/ml/test_simulation.py`

**Interfaces:**
- Consumes: Task 2's `simulate_regular_season`
- Produces:
  - `seed_conference(records: dict[int, list[int]], team_ids: list[int], rng: random.Random) -> list[int]` — team ids ordered 1st to last, ties broken randomly
  - `simulate_series(score_home: Callable[[int, int], float], higher: int, lower: int, rng: random.Random) -> int` — best-of-7 winner; `score_home(home_id, away_id)` returns P(home win)
  - `resolve_play_in(seeds: list[int], score_home: Callable[[int, int], float], rng: random.Random) -> list[int]` — the 8 playoff teams in seed order
  - `SeasonOutcome` dataclass: `records: dict[int, list[int]]`, `seeds: dict[int, int]`, `playoff_teams: set[int]`, `conference_champions: set[int]`, `champion: int`
  - `simulate_season(builder, schedule, score, rng, conferences: dict[int, str]) -> SeasonOutcome`

**Home court:** the higher seed hosts games 1, 2, 5, 7 (the 2-2-1-1-1 pattern).

- [ ] **Step 1: Write the failing tests**

```python
def test_seed_conference_orders_by_wins() -> None:
    from ml.pipeline.simulation import seed_conference

    records = {1: [50, 32], 2: [60, 22], 3: [40, 42]}
    assert seed_conference(records, [1, 2, 3], random.Random(1)) == [2, 1, 3]


def test_seed_conference_breaks_ties_without_crashing() -> None:
    from ml.pipeline.simulation import seed_conference

    records = {1: [41, 41], 2: [41, 41], 3: [41, 41]}
    order = seed_conference(records, [1, 2, 3], random.Random(2))
    assert sorted(order) == [1, 2, 3]


def test_simulate_series_certain_favourite_always_wins() -> None:
    from ml.pipeline.simulation import simulate_series

    # Higher seed hosts 1,2,5,7. If home always wins, the series goes the distance and the
    # higher seed takes game 7, winning 4-3.
    assert simulate_series(lambda _h, _a: 1.0, 1, 8, random.Random(3)) == 1


def test_simulate_series_certain_road_team_wins() -> None:
    from ml.pipeline.simulation import simulate_series

    # Home team always loses: the lower seed wins games 1,2 and the higher seed wins 3,4 ...
    # whichever way it falls, exactly one team must be returned.
    winner = simulate_series(lambda _h, _a: 0.0, 1, 8, random.Random(3))
    assert winner in (1, 8)


def test_resolve_play_in_returns_eight_teams_from_ten() -> None:
    from ml.pipeline.simulation import resolve_play_in

    seeds = list(range(1, 16))
    qualified = resolve_play_in(seeds, lambda _h, _a: 1.0, random.Random(4))
    assert len(qualified) == 8
    # Top six always advance untouched.
    assert qualified[:6] == [1, 2, 3, 4, 5, 6]
    # The last two come from the 7-10 play-in group.
    assert set(qualified[6:]) <= {7, 8, 9, 10}


def test_simulate_season_produces_one_champion_and_sixteen_playoff_teams() -> None:
    import copy
    from datetime import date, timedelta

    from ml.pipeline.features import FeatureBuilder
    from ml.pipeline.simulation import simulate_season

    team_ids = list(range(1, 31))
    conferences = {t: ("East" if t <= 15 else "West") for t in team_ids}
    schedule = []
    gid = 0
    for i, home in enumerate(team_ids):
        for away in team_ids:
            if home == away:
                continue
            gid += 1
            schedule.append(
                ScheduledGame(
                    game_id=gid,
                    season=2026,
                    game_date=date(2026, 10, 20) + timedelta(days=gid % 150),
                    home_team_id=home,
                    visitor_team_id=away,
                )
            )

    outcome = simulate_season(
        copy.deepcopy(FeatureBuilder()), schedule, lambda _f: 0.5, random.Random(9), conferences
    )
    assert len(outcome.playoff_teams) == 16
    assert len(outcome.conference_champions) == 2
    assert outcome.champion in outcome.conference_champions
    assert set(outcome.seeds) == set(team_ids)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings -k "seed_ or series or play_in or simulate_season"`
Expected: FAIL — `ImportError: cannot import name 'seed_conference'`

- [ ] **Step 3: Implement**

Append to `ml/pipeline/simulation.py`:

```python
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
        final_home
        if rng.random() < score_home(final_home, nine_ten_winner)
        else nine_ten_winner
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
    first, second = finalists
    if records[second][0] > records[first][0]:
        first, second = second, first
    champion = simulate_series(score_home, first, second, rng)
    return SeasonOutcome(
        records=records,
        seeds=seeds,
        playoff_teams=playoff_teams,
        conference_champions=set(finalists),
        champion=champion,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings`
Expected: PASS (16 tests)

- [ ] **Step 5: Lint, type-check, commit**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy ml
git add ml/pipeline/simulation.py tests/ml/test_simulation.py
git commit -m "Simulate play-in, conference brackets and the Finals"
```

---

### Task 4: Aggregate many runs into projections

**Files:**
- Modify: `ml/pipeline/simulation.py`
- Test: `tests/ml/test_simulation.py`

**Interfaces:**
- Consumes: Task 3's `SeasonOutcome`, `simulate_season`
- Produces:
  - `TeamProjection` dataclass: `team_id: int`, `proj_wins: float`, `proj_losses: float`, `wins_p10: float`, `wins_p50: float`, `wins_p90: float`, `make_playoffs_pct: float`, `win_conference_pct: float`, `win_title_pct: float`, `avg_seed: float`
  - `aggregate(outcomes: list[SeasonOutcome]) -> list[TeamProjection]`
  - `run_simulations(builder, schedule, predictor, conferences, *, simulations: int, seed: int) -> list[TeamProjection]`

Percentages are 0-100.

- [ ] **Step 1: Write the failing tests**

```python
def test_aggregate_averages_records_and_rates() -> None:
    from ml.pipeline.simulation import SeasonOutcome, aggregate

    outcomes = [
        SeasonOutcome(
            records={1: [60, 20], 2: [20, 60]},
            seeds={1: 1, 2: 2},
            playoff_teams={1},
            conference_champions={1},
            champion=1,
        ),
        SeasonOutcome(
            records={1: [40, 40], 2: [40, 40]},
            seeds={1: 2, 2: 1},
            playoff_teams={1, 2},
            conference_champions={2},
            champion=2,
        ),
    ]
    projections = {p.team_id: p for p in aggregate(outcomes)}

    assert projections[1].proj_wins == 50.0
    assert projections[1].proj_losses == 30.0
    assert projections[1].make_playoffs_pct == 100.0
    assert projections[2].make_playoffs_pct == 50.0
    assert projections[1].win_title_pct == 50.0
    assert projections[2].win_title_pct == 50.0
    assert projections[1].avg_seed == 1.5


def test_aggregate_title_percentages_sum_to_one_hundred() -> None:
    from ml.pipeline.simulation import SeasonOutcome, aggregate

    outcomes = [
        SeasonOutcome(
            records={t: [41, 41] for t in range(1, 5)},
            seeds={t: t for t in range(1, 5)},
            playoff_teams={1, 2},
            conference_champions={1, 2},
            champion=champ,
        )
        for champ in (1, 1, 2, 3)
    ]
    total = sum(p.win_title_pct for p in aggregate(outcomes))
    assert abs(total - 100.0) < 1e-9


def test_aggregate_percentiles_span_the_distribution() -> None:
    from ml.pipeline.simulation import SeasonOutcome, aggregate

    outcomes = [
        SeasonOutcome(
            records={1: [wins, 82 - wins]},
            seeds={1: 1},
            playoff_teams={1},
            conference_champions={1},
            champion=1,
        )
        for wins in range(30, 60)
    ]
    projection = aggregate(outcomes)[0]
    assert projection.wins_p10 < projection.wins_p50 < projection.wins_p90
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings -k aggregate`
Expected: FAIL — `ImportError: cannot import name 'aggregate'`

- [ ] **Step 3: Implement**

Add `import copy` and `from statistics import mean` to the imports, then append:

```python
@dataclass
class TeamProjection:
    """Aggregated projection for one team across many simulated seasons."""

    team_id: int
    proj_wins: float
    proj_losses: float
    wins_p10: float
    wins_p50: float
    wins_p90: float
    make_playoffs_pct: float
    win_conference_pct: float
    win_title_pct: float
    avg_seed: float


def _percentile(sorted_values: list[int], fraction: float) -> float:
    """Nearest-rank percentile. Inputs must already be sorted ascending."""
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, int(round(fraction * (len(sorted_values) - 1)))))
    return float(sorted_values[index])


def aggregate(outcomes: list[SeasonOutcome]) -> list[TeamProjection]:
    """Reduce simulated seasons to per-team means, percentiles and rates."""
    runs = len(outcomes)
    team_ids = sorted({t for outcome in outcomes for t in outcome.records})
    projections: list[TeamProjection] = []

    for team_id in team_ids:
        wins = sorted(o.records[team_id][0] for o in outcomes if team_id in o.records)
        losses = [o.records[team_id][1] for o in outcomes if team_id in o.records]
        seeds = [o.seeds[team_id] for o in outcomes if team_id in o.seeds]
        projections.append(
            TeamProjection(
                team_id=team_id,
                proj_wins=mean(wins),
                proj_losses=mean(losses),
                wins_p10=_percentile(wins, 0.10),
                wins_p50=_percentile(wins, 0.50),
                wins_p90=_percentile(wins, 0.90),
                make_playoffs_pct=100.0
                * sum(1 for o in outcomes if team_id in o.playoff_teams)
                / runs,
                win_conference_pct=100.0
                * sum(1 for o in outcomes if team_id in o.conference_champions)
                / runs,
                win_title_pct=100.0 * sum(1 for o in outcomes if o.champion == team_id) / runs,
                avg_seed=mean(seeds) if seeds else 0.0,
            )
        )
    return projections


def run_simulations(
    builder: FeatureBuilder,
    schedule: list[ScheduledGame],
    predictor: Predictor,
    conferences: dict[int, str],
    *,
    simulations: int,
    seed: int,
) -> list[TeamProjection]:
    """Run ``simulations`` full seasons and aggregate them.

    ``builder`` is treated as immutable seed state — each run gets its own deep copy.
    """
    score = make_scorer(predictor)
    outcomes = [
        simulate_season(
            copy.deepcopy(builder), schedule, score, random.Random(seed + run), conferences
        )
        for run in range(simulations)
    ]
    return aggregate(outcomes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_simulation.py -p no:warnings`
Expected: PASS (19 tests)

- [ ] **Step 5: Lint, type-check, commit**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black ml tests/ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy ml
git add ml/pipeline/simulation.py tests/ml/test_simulation.py
git commit -m "Aggregate simulated seasons into per-team projections"
```

---

### Task 5: `season_projections` table and migration

**Files:**
- Create: `backend/app/models/season_projection.py`
- Create: `backend/alembic/versions/20260827_b1d4e7f9a2c3_add_season_projections.py`
- Modify: `backend/app/models/__init__.py` — add the import **and** an entry in `__all__` (both are required; the file keeps them in sync alphabetically)
- Test: `tests/backend/test_season_projections_api.py` (schema-only assertions for now)

**Interfaces:**
- Produces: `SeasonProjection` ORM model, table `season_projections`, unique constraint `uq_season_projections_season_team_version` on `(season, team_id, model_version)`

- [ ] **Step 1: Write the model**

```python
"""SeasonProjection — Monte Carlo projection for one team in one season.

Written by ``etl.jobs.simulate_season``; read-only everywhere else. Percentages are 0-100.
``model_version`` matches ``model_predictions.model_version`` so projections can be traced to the
model that produced them.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class SeasonProjection(TimestampMixin, Base):
    __tablename__ = "season_projections"
    __table_args__ = (
        UniqueConstraint(
            "season", "team_id", "model_version", name="uq_season_projections_season_team_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    model_version: Mapped[str] = mapped_column(String(64), index=True)

    proj_wins: Mapped[float] = mapped_column(Float)
    proj_losses: Mapped[float] = mapped_column(Float)
    wins_p10: Mapped[float] = mapped_column(Float)
    wins_p50: Mapped[float] = mapped_column(Float)
    wins_p90: Mapped[float] = mapped_column(Float)

    make_playoffs_pct: Mapped[float] = mapped_column(Float)
    win_conference_pct: Mapped[float] = mapped_column(Float)
    win_title_pct: Mapped[float] = mapped_column(Float)
    avg_seed: Mapped[float] = mapped_column(Float)

    simulations: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
```

- [ ] **Step 2: Write the migration**

`down_revision` is `a3ceba4cf6cd` (the initial schema — confirm with `alembic heads` before writing).

```python
"""add season_projections

Revision ID: b1d4e7f9a2c3
Revises: a3ceba4cf6cd
"""

import sqlalchemy as sa
from alembic import op

revision = "b1d4e7f9a2c3"
down_revision = "a3ceba4cf6cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "season_projections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("proj_wins", sa.Float(), nullable=False),
        sa.Column("proj_losses", sa.Float(), nullable=False),
        sa.Column("wins_p10", sa.Float(), nullable=False),
        sa.Column("wins_p50", sa.Float(), nullable=False),
        sa.Column("wins_p90", sa.Float(), nullable=False),
        sa.Column("make_playoffs_pct", sa.Float(), nullable=False),
        sa.Column("win_conference_pct", sa.Float(), nullable=False),
        sa.Column("win_title_pct", sa.Float(), nullable=False),
        sa.Column("avg_seed", sa.Float(), nullable=False),
        sa.Column("simulations", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season", "team_id", "model_version", name="uq_season_projections_season_team_version"
        ),
    )
    op.create_index(
        "ix_season_projections_season", "season_projections", ["season"], unique=False
    )
    op.create_index(
        "ix_season_projections_team_id", "season_projections", ["team_id"], unique=False
    )
    op.create_index(
        "ix_season_projections_model_version",
        "season_projections",
        ["model_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_season_projections_model_version", table_name="season_projections")
    op.drop_index("ix_season_projections_team_id", table_name="season_projections")
    op.drop_index("ix_season_projections_season", table_name="season_projections")
    op.drop_table("season_projections")
```

**Verified:** `TimestampMixin` in `backend/app/models/base.py` defines `created_at` and `updated_at` as timezone-aware, `server_default=CURRENT_TIMESTAMP`, `nullable=False` — exactly as written above, so the migration matches. `updated_at` also carries `onupdate=func.now()`, which is application-side and needs no migration column change.

- [ ] **Step 3: Verify the migration round-trips**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini upgrade head
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini downgrade -1
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini upgrade head
```
Expected: all three succeed with no error.

- [ ] **Step 4: Check for model/migration drift**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini check
```
Expected: "No new upgrade operations detected."

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/season_projection.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "Add season_projections table"
```

---

### Task 6: `simulate_season` ETL job

**Files:**
- Create: `etl/jobs/simulate_season.py`
- Test: `tests/etl/test_simulate_season.py`

**Interfaces:**
- Consumes: Task 4's `run_simulations`, Task 5's `SeasonProjection`, `ml.pipeline.collect.collect_games`, `etl.core.upsert.upsert`, `etl.core.summary.JobSummary`
- Produces: `run(session: AsyncSession, predictor: Predictor | None, *, season: int, simulations: int = 2000, seed: int = 0, now: datetime | None = None) -> JobSummary`

Follow the structure of `etl/jobs/predict_upcoming.py` exactly: no-op when `predictor is None`, build history from all completed games, upsert, commit, log a summary, and provide an `_main()` entrypoint.

- [ ] **Step 1: Write the failing test**

Model it on `tests/etl/test_predict_upcoming.py` — read that file first and reuse its session fixture and seeding helpers.

```python
"""Tests for the season projection job."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.season_projection import SeasonProjection
from etl.jobs import simulate_season


async def test_no_active_model_is_a_no_op(session: AsyncSession) -> None:
    summary = await simulate_season.run(session, None, season=2026, simulations=2)
    assert summary.rows_processed == 0
    rows = (await session.execute(select(SeasonProjection))).scalars().all()
    assert rows == []


async def test_writes_one_row_per_team_and_is_idempotent(
    session: AsyncSession, seeded_predictor: object
) -> None:
    first = await simulate_season.run(
        session, seeded_predictor, season=2026, simulations=3, seed=1
    )
    assert first.rows_processed > 0

    rows = (await session.execute(select(SeasonProjection))).scalars().all()
    team_ids = {r.team_id for r in rows}
    assert len(rows) == len(team_ids)
    for row in rows:
        assert 0.0 <= row.make_playoffs_pct <= 100.0
        assert 0.0 <= row.win_title_pct <= 100.0
        assert row.simulations == 3

    # Re-running must update in place, not duplicate.
    await simulate_season.run(session, seeded_predictor, season=2026, simulations=3, seed=1)
    again = (await session.execute(select(SeasonProjection))).scalars().all()
    assert len(again) == len(rows)
```

Add a `seeded_predictor` fixture to `tests/etl/conftest.py` that seeds teams (with conferences), a small completed-game history, a 2026 schedule, and returns a `Predictor` wrapping a trivial fitted logistic regression — reuse `tests/ml/synth.py` if it already provides one.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_simulate_season.py -p no:warnings`
Expected: FAIL — `ModuleNotFoundError: No module named 'etl.jobs.simulate_season'`

- [ ] **Step 3: Implement the job**

```python
"""Simulate a season many times and store per-team projections.

Reads the active model only — never trains. Idempotent via upsert on
``(season, team_id, model_version)``, so re-running refreshes the projection. No-ops when no
model is active.

Run as: ``python -m etl.jobs.simulate_season``
"""

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.season_projection import SeasonProjection
from backend.app.models.team import Team
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from ml.pipeline.collect import collect_games
from ml.pipeline.features import FeatureBuilder
from ml.pipeline.inference import Predictor
from ml.pipeline.simulation import ScheduledGame, run_simulations

logger = get_logger("etl.simulate_season")

DEFAULT_SIMULATIONS = 2000

UPDATE_COLS = [
    "proj_wins",
    "proj_losses",
    "wins_p10",
    "wins_p50",
    "wins_p90",
    "make_playoffs_pct",
    "win_conference_pct",
    "win_title_pct",
    "avg_seed",
    "simulations",
    "generated_at",
]


async def run(
    session: AsyncSession,
    predictor: Predictor | None,
    *,
    season: int,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = 0,
    now: datetime | None = None,
) -> JobSummary:
    started = time.monotonic()
    summary = JobSummary(job="simulate_season")

    if predictor is None:
        logger.info("etl.simulate_season.no_active_model")
        summary.duration_ms = int((time.monotonic() - started) * 1000)
        return summary

    stamp = now or datetime.now(UTC)

    conferences = {
        team.id: team.conference
        for team in (await session.execute(select(Team))).scalars().all()
    }

    scheduled = (
        (
            await session.execute(
                select(Game)
                .where(Game.season == season)
                .where(func.lower(Game.status) != "final")
                .where(Game.postseason.is_(False))
                .order_by(Game.game_date, Game.id)
            )
        )
        .scalars()
        .all()
    )
    if not scheduled:
        logger.info("etl.simulate_season.no_schedule", season=season)
        summary.duration_ms = int((time.monotonic() - started) * 1000)
        return summary

    schedule = [
        ScheduledGame(
            game_id=g.id,
            season=g.season,
            game_date=g.game_date,
            home_team_id=g.home_team_id,
            visitor_team_id=g.visitor_team_id,
        )
        for g in scheduled
    ]

    builder = FeatureBuilder()
    for record in await collect_games(session):
        builder.observe(record)

    projections = run_simulations(
        builder, schedule, predictor, conferences, simulations=simulations, seed=seed
    )

    rows: list[dict[str, Any]] = [
        {
            "season": season,
            "team_id": p.team_id,
            "model_version": predictor.model_version,
            "proj_wins": p.proj_wins,
            "proj_losses": p.proj_losses,
            "wins_p10": p.wins_p10,
            "wins_p50": p.wins_p50,
            "wins_p90": p.wins_p90,
            "make_playoffs_pct": p.make_playoffs_pct,
            "win_conference_pct": p.win_conference_pct,
            "win_title_pct": p.win_title_pct,
            "avg_seed": p.avg_seed,
            "simulations": simulations,
            "generated_at": stamp,
        }
        for p in projections
    ]

    try:
        summary.rows_processed = await upsert(
            session,
            SeasonProjection,
            rows,
            ["season", "team_id", "model_version"],
            UPDATE_COLS,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    summary.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info("etl.job.summary", **summary.as_dict())
    return summary


async def _main() -> int:
    from backend.app.core.logging import configure_logging
    from backend.app.db.session import SessionLocal
    from ml.pipeline.inference import load_active_predictor

    configure_logging()
    predictor = load_active_predictor()
    season = int(os.getenv("PROJECTION_SEASON", "2026"))
    simulations = int(os.getenv("PROJECTION_SIMULATIONS", str(DEFAULT_SIMULATIONS)))
    async with SessionLocal() as session:
        summary = await run(session, predictor, season=season, simulations=simulations)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_simulate_season.py -p no:warnings`
Expected: PASS (2 tests)

- [ ] **Step 5: Lint, type-check, commit**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check etl tests/etl
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black etl tests/etl
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy etl
git add etl/jobs/simulate_season.py tests/etl/
git commit -m "Add simulate_season job writing per-team projections"
```

---

### Task 7: Projections API endpoint

**Files:**
- Create: `backend/app/schemas/projection.py`
- Create: `backend/app/services/projections.py`
- Create: `backend/app/api/v1/projections.py`
- Modify: `backend/app/api/v1/router.py` (register the new router)
- Test: `tests/backend/test_season_projections_api.py`

**Interfaces:**
- Consumes: Task 5's `SeasonProjection`
- Produces: `GET /api/v1/projections?season=<int>` returning `{"data": [...], "meta": {...}}`

Read `backend/app/api/v1/standings.py`, `backend/app/services/standings.py`, and `backend/app/schemas/standing.py` first and mirror their structure, including the caching decorator if standings uses one. Each projection embeds its team, matching how standings embeds team data (if standings returns a bare `team_id`, do the same — consistency with the existing surface matters more than embedding).

- [ ] **Step 1: Write the failing test**

```python
async def test_projections_returns_rows_for_a_season(client, seeded_projections) -> None:
    response = await client.get("/api/v1/projections?season=2026")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] > 0
    first = body["data"][0]
    assert first["season"] == 2026
    assert 0.0 <= first["win_title_pct"] <= 100.0
    # Ordered strongest-first.
    wins = [row["proj_wins"] for row in body["data"]]
    assert wins == sorted(wins, reverse=True)


async def test_projections_empty_for_unknown_season(client, seeded_projections) -> None:
    response = await client.get("/api/v1/projections?season=1999")
    assert response.status_code == 200
    assert response.json()["data"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/backend/test_season_projections_api.py -p no:warnings`
Expected: FAIL — 404, because the route does not exist.

- [ ] **Step 3: Implement schema, service and router**

```python
# backend/app/schemas/projection.py
"""Response schema for season projections."""

from pydantic import BaseModel, ConfigDict


class ProjectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    team_id: int
    model_version: str
    proj_wins: float
    proj_losses: float
    wins_p10: float
    wins_p50: float
    wins_p90: float
    make_playoffs_pct: float
    win_conference_pct: float
    win_title_pct: float
    avg_seed: float
    simulations: int
```

```python
# backend/app/services/projections.py
"""Read season projections. Written offline by etl.jobs.simulate_season."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.season_projection import SeasonProjection


async def list_projections(
    session: AsyncSession, *, season: int, limit: int, offset: int
) -> tuple[list[SeasonProjection], int]:
    """Return projections for a season ordered by projected wins, plus the total count."""
    base = select(SeasonProjection).where(SeasonProjection.season == season)
    total = (
        await session.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(SeasonProjection.proj_wins.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)
```

The router mirrors `standings.py`: a thin `@router.get("")` that reads query params (`season`, `limit`, `offset`), calls `list_projections`, and returns the `{data, meta}` envelope the other list endpoints use. Register it in `router.py` alongside the existing includes, with prefix `/projections` and tag `projections`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/backend -p no:warnings`
Expected: PASS, including the two new tests.

- [ ] **Step 5: Full backend gates, commit**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check .
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check .
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest --cov=backend --cov-fail-under=80 -p no:warnings
git add backend/ tests/backend/
git commit -m "Serve season projections from /api/v1/projections"
```

---

### Task 8: Season Projection page

**Files:**
- Modify: `frontend/src/api/types.ts` (add `Projection`)
- Create: `frontend/src/hooks/useProjections.ts`
- Create: `frontend/src/pages/SeasonProjection.tsx`
- Modify: `frontend/src/App.tsx` (add the `projection` route)
- Modify: `frontend/src/components/Layout.tsx` (add the nav link)
- Test: `frontend/src/pages/SeasonProjection.test.tsx`

**Interfaces:**
- Consumes: Task 7's `GET /api/v1/projections`
- Produces: route `/projection`, nav label "Projection"

Read `frontend/src/pages/Teams.tsx` and `frontend/src/pages/Teams.test.tsx` first and follow their structure exactly — `PageHeader`, `SectionTitle`, `Card`, `TeamMark`, `DataTable`, `QueryState`, `teamColor`, and `MemoryRouter` in the test.

- [ ] **Step 1: Add the type and hook**

```ts
// frontend/src/api/types.ts — add alongside the existing interfaces
export interface Projection {
  id: number;
  season: number;
  team_id: number;
  model_version: string;
  proj_wins: number;
  proj_losses: number;
  wins_p10: number;
  wins_p50: number;
  wins_p90: number;
  make_playoffs_pct: number;
  win_conference_pct: number;
  win_title_pct: number;
  avg_seed: number;
  simulations: number;
}
```

```ts
// frontend/src/hooks/useProjections.ts
import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { Projection } from "../api/types";

export function useProjections(season: number) {
  return useQuery({
    queryKey: ["projections", season],
    queryFn: () => apiGet<Paged<Projection>>("/projections", { season, limit: 50 }),
  });
}
```

- [ ] **Step 2: Write the failing page test**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import SeasonProjection from "./SeasonProjection";

vi.mock("../hooks/useProjections", () => ({
  useProjections: () => ({
    data: {
      data: [
        {
          id: 1,
          season: 2026,
          team_id: 37,
          model_version: "m.pkl",
          proj_wins: 55.2,
          proj_losses: 24.8,
          wins_p10: 49,
          wins_p50: 55,
          wins_p90: 61,
          make_playoffs_pct: 92.5,
          win_conference_pct: 24.0,
          win_title_pct: 12.5,
          avg_seed: 2.4,
          simulations: 2000,
        },
      ],
      meta: { total: 1 },
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/useTeams", () => ({
  useTeams: () => ({
    data: {
      data: [
        {
          id: 37,
          abbreviation: "ATL",
          name: "Hawks",
          full_name: "Atlanta Hawks",
          city: "Atlanta",
          conference: "East",
          division: "Southeast",
        },
      ],
      meta: { total: 1 },
    },
    isLoading: false,
    isError: false,
  }),
}));

describe("SeasonProjection", () => {
  it("renders a team's projected record and title odds", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <SeasonProjection />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText(/Atlanta Hawks|ATL/)).toBeInTheDocument();
    expect(screen.getByText(/55-25|55.2/)).toBeInTheDocument();
    expect(screen.getByText(/12.5%/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/SeasonProjection.test.tsx`
Expected: FAIL — cannot resolve `./SeasonProjection`

- [ ] **Step 4: Build the page**

`SeasonProjection.tsx` joins projections to teams by `team_id`, splits by `team.conference`, and renders:
1. `PageHeader` — eyebrow "THE SEASON AHEAD", title "Season Projection", subtitle naming the simulation count and the 80-game schedule
2. A short note: projections carry team strength forward from prior seasons only — no roster changes, trades, draft, or injuries
3. Title-odds leaderboard: top 10 by `win_title_pct`, each row a `TeamMark` plus a `teamColor`-tinted bar
4. Two conference tables via `DataTable`: team, projected record (`proj_wins` rounded, `proj_losses` rounded), a p10-p90 range bar, `make_playoffs_pct`, `win_title_pct`
5. `QueryState` wrapping loading and error states

Round records for display with `Math.round`. Format percentages with the existing `formatPct` helper in `src/lib/format.ts` if its contract matches (check whether it expects a 0-1 fraction or a 0-100 number — the API returns 0-100).

- [ ] **Step 5: Wire the route and nav**

Add `{ path: "projection", element: <SeasonProjection /> }` to the children array in `App.tsx`, and a matching `NavLink` labelled "Projection" in `Layout.tsx`, following the existing entries.

- [ ] **Step 6: Run the full frontend gates**

```bash
cd frontend
npm run lint && npm run typecheck && npm run test && npm run build
```
Expected: all pass, 5 tests total.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "Add Season Projection page"
```

---

### Task 9: Generate real projections and verify end to end

**Files:** none — this task runs the job and checks the result.

- [ ] **Step 1: Run the job against the local database**

Docker must be running. Start with a small run to check wiring before committing to 2,000.

```bash
docker compose -f docker/docker-compose.yml up -d
PROJECTION_SIMULATIONS=25 PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run python -m etl.jobs.simulate_season
```
Expected: a summary log with `rows_processed=30`.

- [ ] **Step 2: Sanity-check the output**

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U nba -d nba -c "select round(sum(win_title_pct)::numeric,1) title_total, round(sum(proj_wins)::numeric,0) total_wins, count(*) teams from season_projections where season=2026;"
```
Expected: `title_total` = 100.0, `teams` = 30, and `total_wins` = 1200 (every game produces exactly one winner, so projected wins must sum to the number of games).

If `total_wins` is not 1200, the simulation is dropping or double-counting games — stop and diagnose before proceeding.

- [ ] **Step 3: Run the full 2,000 simulations**

```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run python -m etl.jobs.simulate_season
```
Note the wall-clock time. If it exceeds ~15 minutes, reduce `DEFAULT_SIMULATIONS` to 1,000 and record the change in the spec's simplifications.

- [ ] **Step 4: Verify the page renders**

```bash
docker compose -f docker/docker-compose.yml up -d --build backend frontend
docker compose -f docker/docker-compose.yml exec -T redis redis-cli FLUSHALL
```
Open http://localhost:5173/projection and confirm the leaderboard and both conference tables populate.

- [ ] **Step 5: Load the projections into Neon and confirm live**

```bash
docker compose -f docker/docker-compose.yml exec -T db pg_dump -U nba -d nba --no-owner --no-acl -t season_projections -f /tmp/proj.sql
```
Then restore that single table into Neon using the same `psql "$PGURL"` approach used for the initial data load, and confirm `https://nba-dashboard-eezf.onrender.com/api/v1/projections?season=2026` returns 30 rows.

Note: prefix the `docker compose exec` commands with `MSYS_NO_PATHCONV=1` in Git Bash, or `/tmp/...` is rewritten to a Windows path.

- [ ] **Step 6: Commit any adjustments and open the PR**

```bash
git add -A
git commit -m "Generate 2026-27 season projections"
git push -u origin feat/season-projection
```

---

## Self-Review Notes

Checked against the spec:

- Monte Carlo with evolving Elo — Tasks 2, 3
- Play-in plus best-of-7 bracket and Finals — Task 3
- Random tiebreakers, documented — Task 3 (`seed_conference`)
- 2,000 simulations default, offline only — Tasks 4, 6
- `season_projections` columns exactly as specified — Task 5
- `GET /api/v1/projections?season=` — Task 7
- Page with projected standings, title leaderboard, p10-p90 range bars, and the no-roster note — Task 8
- Determinism under a seed, play-in/bracket logic, title percentages summing to 100, 16 playoff teams, API contract, page render — Tasks 1-4, 6-8

Two checks were added beyond the spec because they catch whole classes of error cheaply: projected wins summing to the game count (Task 9 Step 2), and the fast scorer matching `predict_proba` (Task 1).
