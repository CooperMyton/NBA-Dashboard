# Current Rosters and Player Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the all-time player list on team pages with real 2026-27 rosters, add season stats, and flag players primed to break out or regress.

**Architecture:** A local-only ETL job pulls current rosters and four seasons of player stats from `nba_api`, matches them to existing player rows by name in two passes, and stores season stats plus precomputed breakout/regression flags. The API exposes an `active` filter and an insights endpoint; the Players page and team detail render both.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, Alembic, FastAPI, pytest, React 18 + TypeScript + TanStack Query + Vitest, `nba_api`.

## Global Constraints

- Line length 100 (`ruff`, `black`). Run `ruff check .`, `black --check .`, `mypy backend etl ml` before every commit.
- `mypy --strict` clean — every function annotated, no implicit `Any`.
- Backend coverage gate: 80% minimum (`pytest --cov=backend --cov-fail-under=80`).
- All datetimes UTC via `datetime.now(UTC)`.
- Season integers use the start-year convention: `2026` means 2026-27.
- Business logic lives in services and jobs; routers stay thin.
- Migrations are the only schema path, with a tested downgrade.
- No test performs network access. `nba_api` is imported only by `etl/providers/nba_stats.py`.
- Prefix every backend command with `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run`.

---

## File Structure

**Create:**
- `etl/core/names.py` — name normalisation and two-pass matching (pure functions)
- `ml/pipeline/player_signals.py` — breakout/regression computation (pure functions)
- `backend/app/models/player_season_stat.py` — `PlayerSeasonStat` ORM model
- `backend/app/models/player_insight.py` — `PlayerInsight` ORM model
- `backend/alembic/versions/<rev>_add_player_season_stats_and_insights.py`
- `etl/providers/nba_stats.py` — the only `nba_api` importer
- `backend/app/schemas/player_insight.py` — `PlayerInsightOut`
- `backend/app/services/player_insights.py` — insight queries
- `etl/jobs/sync_rosters.py` — orchestrating job
- `frontend/src/hooks/usePlayerInsights.ts`
- Tests: `tests/etl/test_names.py`, `tests/ml/test_player_signals.py`, `tests/etl/test_sync_rosters.py`, `tests/backend/test_player_insights_api.py`, `frontend/src/pages/Players.test.tsx`

**Modify:**
- `backend/app/models/player.py` — add `nba_player_id`, `roster_season`
- `backend/app/schemas/player.py` — expose new fields plus latest stats
- `backend/app/services/players.py` — `active` filter
- `backend/app/api/v1/players.py` — `active` query param, insights route declared **before** `/{player_id}`
- `backend/app/core/cache.py` — add `PLAYER_INSIGHTS_PREFIX`
- `pyproject.toml` — add `nba_api`
- `frontend/src/api/types.ts`, `frontend/src/hooks/usePlayers.ts`, `frontend/src/pages/Players.tsx`, `frontend/src/pages/TeamDetail.tsx`

---

## Task 1: Name matching

**Files:**
- Create: `etl/core/names.py`
- Test: `tests/etl/test_names.py`

**Interfaces:**
- Produces: `normalize_name(value: str) -> str`, `match_players(nba_names: list[tuple[int, str, str]], db_players: list[tuple[int, str, str]]) -> tuple[dict[int, int], list[int]]` where each input tuple is `(id, full_name, team_abbr)`; returns `(nba_id -> db_player_id, unmatched_nba_ids)`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for player name normalisation and matching."""

from etl.core.names import match_players, normalize_name


def test_normalize_strips_case_punctuation_and_accents() -> None:
    assert normalize_name("A.J. Lawson") == "aj lawson"
    assert normalize_name("Luka Don\u010di\u0107") == "luka doncic"
    assert normalize_name("Jaren Jackson Jr.") == "jaren jackson"
    assert normalize_name("Nigel Hayes-Davis") == "nigel hayes davis"


def test_match_players_pairs_on_exact_normalized_name() -> None:
    nba = [(1, "Luka Doncic", "LAL")]
    db = [(50, "Luka Don\u010di\u0107", "LAL")]
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_names.py -p no:warnings`
Expected: FAIL with `ModuleNotFoundError: No module named 'etl.core.names'`

- [ ] **Step 3: Write the implementation**

```python
"""Match players between providers by name.

``nba_api`` keys players by NBA's id; the database keys them by balldontlie's. There is no shared
identifier, so the first sync pairs them by name. Exact normalised full-name matching covers about
98.6% of an NBA season; the remainder are nickname-versus-legal-name cases ("Nic Claxton" against
Nicolas), which a second pass resolves using last name plus current team.
"""

import re
import unicodedata

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def normalize_name(value: str) -> str:
    """Lowercase, strip accents and punctuation, and drop generational suffixes."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    folded = folded.lower().replace(".", "").replace("'", "").replace("-", " ")
    folded = _SUFFIXES.sub("", folded)
    return " ".join(folded.split())


def _last_name(value: str) -> str:
    parts = normalize_name(value).split()
    return parts[-1] if parts else ""


def match_players(
    nba_names: list[tuple[int, str, str]],
    db_players: list[tuple[int, str, str]],
) -> tuple[dict[int, int], list[int]]:
    """Pair NBA players to database players.

    Each input tuple is ``(id, full_name, team_abbr)``. Returns the mapping from NBA id to database
    player id, plus the NBA ids that could not be paired. A database player is never assigned twice.
    """
    by_full: dict[str, list[int]] = {}
    by_last_team: dict[tuple[str, str], list[int]] = {}
    for db_id, name, team in db_players:
        by_full.setdefault(normalize_name(name), []).append(db_id)
        by_last_team.setdefault((_last_name(name), team.upper()), []).append(db_id)

    matched: dict[int, int] = {}
    taken: set[int] = set()
    unmatched: list[int] = []

    # Pass 1: exact normalised full name.
    deferred: list[tuple[int, str, str]] = []
    for nba_id, name, team in nba_names:
        candidates = [c for c in by_full.get(normalize_name(name), []) if c not in taken]
        if len(candidates) == 1:
            matched[nba_id] = candidates[0]
            taken.add(candidates[0])
        else:
            deferred.append((nba_id, name, team))

    # Pass 2: last name plus team. Ambiguous groups are left unmatched rather than guessed.
    for nba_id, name, team in deferred:
        key = (_last_name(name), team.upper())
        candidates = [c for c in by_last_team.get(key, []) if c not in taken]
        if len(candidates) == 1:
            matched[nba_id] = candidates[0]
            taken.add(candidates[0])
        else:
            unmatched.append(nba_id)

    return matched, unmatched
```

- [ ] **Step 4: Run tests and the gates**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_names.py -p no:warnings`
Expected: PASS (7 tests)

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml`
Expected: all clean

- [ ] **Step 5: Commit**

```bash
git add etl/core/names.py tests/etl/test_names.py
git commit -m "Add two-pass player name matching"
```

---

## Task 2: Breakout and regression signals

**Files:**
- Create: `ml/pipeline/player_signals.py`
- Test: `tests/ml/test_player_signals.py`

**Interfaces:**
- Produces: `SeasonLine` dataclass with fields `season: int`, `games_played: int`, `minutes: float`, `points: float`, `rebounds: float`, `assists: float`, `fg3_pct: float`, `fg3a: float`, `ts_pct: float`, `usage_pct: float`; `Insight` dataclass with `kind: str`, `score: float`, `detail: str`; `regression_signal(lines: list[SeasonLine]) -> Insight | None`; `breakout_signal(lines: list[SeasonLine], *, age: float, experience: int) -> Insight | None`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for breakout and regression signals."""

from ml.pipeline.player_signals import SeasonLine, breakout_signal, regression_signal


def line(
    season: int,
    *,
    gp: int = 70,
    minutes: float = 30.0,
    points: float = 15.0,
    rebounds: float = 5.0,
    assists: float = 4.0,
    fg3_pct: float = 0.350,
    fg3a: float = 5.0,
    ts_pct: float = 0.560,
    usage: float = 0.220,
) -> SeasonLine:
    return SeasonLine(
        season=season,
        games_played=gp,
        minutes=minutes,
        points=points,
        rebounds=rebounds,
        assists=assists,
        fg3_pct=fg3_pct,
        fg3a=fg3a,
        ts_pct=ts_pct,
        usage_pct=usage,
    )


def test_regression_flags_shooting_far_above_baseline() -> None:
    lines = [line(2023, fg3_pct=0.340), line(2024, fg3_pct=0.350), line(2025, fg3_pct=0.430)]
    insight = regression_signal(lines)
    assert insight is not None
    assert insight.kind == "regression"
    assert insight.score > 0
    assert ".430" in insight.detail


def test_regression_flags_bounce_back_with_negative_score() -> None:
    lines = [line(2023, fg3_pct=0.400), line(2024, fg3_pct=0.400), line(2025, fg3_pct=0.300)]
    insight = regression_signal(lines)
    assert insight is not None
    assert insight.score < 0


def test_regression_ignores_small_deviation() -> None:
    lines = [line(2024, fg3_pct=0.350), line(2025, fg3_pct=0.360)]
    assert regression_signal(lines) is None


def test_regression_requires_a_prior_season() -> None:
    assert regression_signal([line(2025, fg3_pct=0.430)]) is None


def test_regression_requires_minimum_games_and_attempts() -> None:
    few_games = [line(2024), line(2025, gp=19, fg3_pct=0.430)]
    assert regression_signal(few_games) is None
    # 1.0 attempt over 70 games is 70 attempts, below the 100 threshold.
    few_attempts = [line(2024), line(2025, fg3a=1.0, fg3_pct=0.430)]
    assert regression_signal(few_attempts) is None


def test_regression_baseline_is_volume_weighted() -> None:
    # A high-volume .330 season should outweigh a low-volume .500 season in the baseline.
    lines = [
        line(2023, fg3_pct=0.330, fg3a=10.0),
        line(2024, fg3_pct=0.500, fg3a=1.0),
        line(2025, fg3_pct=0.400),
    ]
    insight = regression_signal(lines)
    assert insight is not None
    assert insight.score > 0


def test_breakout_flags_young_rising_player() -> None:
    lines = [
        line(2024, minutes=18.0, points=6.0, rebounds=2.0, assists=1.0, usage=0.160),
        line(2025, minutes=28.0, points=15.0, rebounds=4.0, assists=3.0, usage=0.230),
    ]
    insight = breakout_signal(lines, age=22.0, experience=2)
    assert insight is not None
    assert insight.kind == "breakout"
    assert insight.score > 0


def test_breakout_requires_youth_or_inexperience() -> None:
    lines = [
        line(2024, minutes=18.0, points=6.0, usage=0.160),
        line(2025, minutes=28.0, points=15.0, usage=0.230),
    ]
    assert breakout_signal(lines, age=31.0, experience=10) is None


def test_breakout_requires_all_three_to_rise() -> None:
    # Minutes and usage rise but per-36 production falls.
    lines = [
        line(2024, minutes=18.0, points=14.0, rebounds=5.0, assists=4.0, usage=0.160),
        line(2025, minutes=28.0, points=15.0, rebounds=4.0, assists=3.0, usage=0.230),
    ]
    assert breakout_signal(lines, age=22.0, experience=2) is None


def test_breakout_requires_a_prior_season() -> None:
    assert breakout_signal([line(2025)], age=21.0, experience=0) is None


def test_breakout_qualifies_on_experience_alone() -> None:
    lines = [
        line(2024, minutes=18.0, points=6.0, rebounds=2.0, assists=1.0, usage=0.160),
        line(2025, minutes=28.0, points=15.0, rebounds=4.0, assists=3.0, usage=0.230),
    ]
    assert breakout_signal(lines, age=26.0, experience=2) is not None


def test_breakout_handles_zero_minutes_without_dividing_by_zero() -> None:
    lines = [line(2024, minutes=0.0), line(2025, minutes=28.0)]
    assert breakout_signal(lines, age=22.0, experience=1) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_player_signals.py -p no:warnings`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.pipeline.player_signals'`

- [ ] **Step 3: Write the implementation**

```python
"""Breakout and regression signals from player season lines.

Two deliberately transparent signals, each reporting the numbers that produced it so the UI can
justify every flag (docs/superpowers/specs/2026-08-30-current-rosters-and-player-insights-design.md).

Regression compares a player's most recent shooting to their own volume-weighted baseline —
shooting far above your established rate tends not to hold. Breakout looks for a young player
whose minutes, usage and per-36 production are all rising.
"""

from dataclasses import dataclass

# A shooting swing of four percentage points is large enough to be worth surfacing.
REGRESSION_THRESHOLD_PCT = 4.0
MIN_GAMES = 20
MIN_THREE_ATTEMPTS = 100
BREAKOUT_MAX_AGE = 24.0
BREAKOUT_MAX_EXPERIENCE = 3


@dataclass(frozen=True)
class SeasonLine:
    season: int
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    fg3_pct: float
    fg3a: float
    ts_pct: float
    usage_pct: float

    @property
    def three_attempts(self) -> float:
        return self.fg3a * self.games_played

    @property
    def per36(self) -> float:
        """Points, rebounds and assists per 36 minutes; 0.0 when the player did not play."""
        if self.minutes <= 0:
            return 0.0
        return (self.points + self.rebounds + self.assists) * 36.0 / self.minutes


@dataclass(frozen=True)
class Insight:
    kind: str
    score: float
    detail: str


def _sorted(lines: list[SeasonLine]) -> list[SeasonLine]:
    return sorted(lines, key=lambda line: line.season)


def regression_signal(lines: list[SeasonLine]) -> Insight | None:
    """Flag a player shooting far from their own volume-weighted baseline."""
    ordered = _sorted(lines)
    if len(ordered) < 2:
        return None

    recent, prior = ordered[-1], ordered[:-1]
    if recent.games_played < MIN_GAMES or recent.three_attempts < MIN_THREE_ATTEMPTS:
        return None

    weight = sum(line.three_attempts for line in prior)
    if weight <= 0:
        return None
    baseline = sum(line.fg3_pct * line.three_attempts for line in prior) / weight

    score = (recent.fg3_pct - baseline) * 100.0
    if abs(score) < REGRESSION_THRESHOLD_PCT:
        return None

    detail = (
        f"3P% {recent.fg3_pct:.3f} against a {baseline:.3f} baseline "
        f"on {recent.fg3a:.1f} attempts per game"
    )
    return Insight(kind="regression", score=score, detail=detail)


def breakout_signal(lines: list[SeasonLine], *, age: float, experience: int) -> Insight | None:
    """Flag a young player whose minutes, usage and per-36 production are all rising."""
    ordered = _sorted(lines)
    if len(ordered) < 2:
        return None
    if age > BREAKOUT_MAX_AGE and experience > BREAKOUT_MAX_EXPERIENCE:
        return None

    recent, previous = ordered[-1], ordered[-2]
    if previous.minutes <= 0 or recent.minutes <= 0:
        return None

    rising = (
        recent.minutes > previous.minutes
        and recent.usage_pct > previous.usage_pct
        and recent.per36 > previous.per36
    )
    if not rising:
        return None

    score = recent.per36 - previous.per36
    detail = (
        f"{previous.minutes:.1f} to {recent.minutes:.1f} minutes, "
        f"usage {previous.usage_pct:.3f} to {recent.usage_pct:.3f}, "
        f"per-36 {previous.per36:.1f} to {recent.per36:.1f}"
    )
    return Insight(kind="breakout", score=score, detail=detail)
```

- [ ] **Step 4: Run tests and the gates**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/ml/test_player_signals.py -p no:warnings`
Expected: PASS (12 tests)

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml`
Expected: all clean

- [ ] **Step 5: Commit**

```bash
git add ml/pipeline/player_signals.py tests/ml/test_player_signals.py
git commit -m "Add breakout and regression player signals"
```

---

## Task 3: Schema and migration

**Files:**
- Modify: `backend/app/models/player.py`
- Create: `backend/app/models/player_season_stat.py`, `backend/app/models/player_insight.py`
- Create: `backend/alembic/versions/<rev>_add_player_season_stats_and_insights.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Player.nba_player_id: int | None`, `Player.roster_season: int | None`; `PlayerSeasonStat` with columns `id, player_id, season, team_id, games_played, minutes, points, rebounds, assists, fg3_pct, fg3a, ts_pct, usage_pct`; `PlayerInsight` with `id, player_id, season, kind, score, detail, generated_at`.

- [ ] **Step 1: Add the two columns to `Player`**

In `backend/app/models/player.py`, after the `country` column and before `team_id`:

```python
    # NBA's own player id, populated by the roster sync. Lets later syncs join on a stable key
    # instead of repeating name matching.
    nba_player_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    # The season this player is rostered for (start-year convention). Null for historical players.
    roster_season: Mapped[int | None] = mapped_column(index=True)
```

- [ ] **Step 2: Create `backend/app/models/player_season_stat.py`**

```python
"""PlayerSeasonStat — one aggregated season line per player.

Sourced from nba_api's league dashboards (docs/decisions.md D-006 covers why the per-game
``player_stats`` table stays empty: box scores are paid-tier on balldontlie).
"""

from sqlalchemy import Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class PlayerSeasonStat(TimestampMixin, Base):
    __tablename__ = "player_season_stats"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_stats_player_season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(index=True)
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    games_played: Mapped[int] = mapped_column()
    minutes: Mapped[float] = mapped_column(Float)
    points: Mapped[float] = mapped_column(Float)
    rebounds: Mapped[float] = mapped_column(Float)
    assists: Mapped[float] = mapped_column(Float)
    fg3_pct: Mapped[float] = mapped_column(Float)
    fg3a: Mapped[float] = mapped_column(Float)
    ts_pct: Mapped[float] = mapped_column(Float)
    usage_pct: Mapped[float] = mapped_column(Float)
```

- [ ] **Step 3: Create `backend/app/models/player_insight.py`**

```python
"""PlayerInsight — a precomputed breakout or regression flag for a rostered player.

Computed by ``etl.jobs.sync_rosters`` rather than per request, mirroring ``season_projections``.
``detail`` carries the numbers behind the flag so the UI never shows a bare label.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class PlayerInsight(TimestampMixin, Base):
    __tablename__ = "player_insights"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "kind", name="uq_player_insights_player_season_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    score: Mapped[float] = mapped_column(Float)
    detail: Mapped[str] = mapped_column(String(256))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
```

- [ ] **Step 4: Register the models so Alembic sees them**

Add to `backend/app/models/__init__.py` alongside the existing imports:

```python
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.player_season_stat import PlayerSeasonStat
```

Add both names to the module's `__all__` list.

- [ ] **Step 5: Generate the migration**

Run:
```bash
docker compose -f docker/docker-compose.yml up -d db
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini revision --autogenerate -m "add player season stats and insights"
```

Open the generated file and verify it creates both tables, adds the two `players` columns, and that `downgrade()` drops them in reverse order. Autogenerate sometimes omits index drops — add any missing `op.drop_index` calls to `downgrade()`.

- [ ] **Step 6: Verify the migration round-trips**

Run:
```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini upgrade head
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini downgrade -1
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini upgrade head
```
Expected: all three succeed with no error.

Then confirm no drift:
```bash
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini check
```
Expected: "No new upgrade operations detected."

- [ ] **Step 7: Run the gates and commit**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest -p no:warnings`
Expected: all clean, all tests pass

```bash
git add backend/app/models/ backend/alembic/versions/
git commit -m "Add player_season_stats and player_insights tables"
```

---

## Task 4: nba_api provider wrapper

**Files:**
- Create: `etl/providers/nba_stats.py`, `etl/providers/__init__.py` (if absent)
- Modify: `pyproject.toml`
- Test: `tests/etl/test_nba_stats.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RosterEntry` dataclass with `nba_player_id: int`, `name: str`, `team_abbr: str`, `position: str | None`, `jersey: str | None`, `age: float`, `experience: int`; `StatLine` dataclass with `nba_player_id: int`, `name: str`, `team_abbr: str`, `season: int`, and the same numeric fields as `SeasonLine`; `fetch_rosters(season: int, team_nba_ids: dict[str, int]) -> list[RosterEntry]`; `fetch_season_stats(season: int) -> list[StatLine]`; `parse_experience(value: str) -> int`.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to `[project].dependencies`:

```toml
    "nba-api>=1.10",
```

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv lock && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv sync`

- [ ] **Step 2: Write the failing test**

Only the pure parsing helpers are unit-tested; the two fetch functions are thin I/O wrappers exercised by the job test in Task 5 with a stubbed provider.

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_nba_stats.py -p no:warnings`
Expected: FAIL with `ModuleNotFoundError: No module named 'etl.providers.nba_stats'`

- [ ] **Step 4: Write the implementation**

Create `etl/providers/__init__.py` as an empty file, then `etl/providers/nba_stats.py`:

```python
"""nba_api access — the only module that imports it.

balldontlie's free tier has no season dimension for players, so rosters and player stats come from
stats.nba.com instead. The NBA blocks datacenter IP ranges, so anything calling this module runs
from a developer machine, never from CI or the deployed host.
"""

import time
from dataclasses import dataclass
from typing import Any

from nba_api.stats.endpoints import commonteamroster, leaguedashplayerstats

from backend.app.core.logging import get_logger

logger = get_logger("etl.nba_stats")

# stats.nba.com is unofficial and rate-sensitive; pace requests rather than risk a soft ban.
_REQUEST_DELAY_S = 0.7
_TIMEOUT_S = 60


@dataclass(frozen=True)
class RosterEntry:
    nba_player_id: int
    name: str
    team_abbr: str
    position: str | None
    jersey: str | None
    age: float
    experience: int


@dataclass(frozen=True)
class StatLine:
    nba_player_id: int
    name: str
    team_abbr: str
    season: int
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    fg3_pct: float
    fg3a: float
    ts_pct: float
    usage_pct: float


def season_label(season: int) -> str:
    """2026 -> '2026-27', matching the NBA's season string format."""
    return f"{season}-{str(season + 1)[-2:]}"


def parse_experience(value: str) -> int:
    """'R' means rookie; otherwise a year count. Anything unrecognised counts as zero."""
    text = str(value).strip().upper()
    if text == "R":
        return 0
    try:
        return int(text)
    except ValueError:
        return 0


def _num(row: dict[str, Any], key: str) -> float:
    value = row.get(key)
    return 0.0 if value is None else float(value)


def rows_to_stat_lines(
    base: list[dict[str, Any]], advanced: list[dict[str, Any]], *, season: int
) -> list[StatLine]:
    """Join the Base and Advanced dashboards on player id.

    A player present in Base but absent from Advanced is skipped rather than defaulted — a missing
    Advanced row means the two dashboards disagree, and inventing TS%/usage would corrupt the
    signals downstream.
    """
    adv_by_id = {int(row["PLAYER_ID"]): row for row in advanced}
    lines: list[StatLine] = []
    for row in base:
        pid = int(row["PLAYER_ID"])
        adv = adv_by_id.get(pid)
        if adv is None:
            continue
        lines.append(
            StatLine(
                nba_player_id=pid,
                name=str(row["PLAYER_NAME"]),
                team_abbr=str(row["TEAM_ABBREVIATION"]),
                season=season,
                games_played=int(row.get("GP") or 0),
                minutes=_num(row, "MIN"),
                points=_num(row, "PTS"),
                rebounds=_num(row, "REB"),
                assists=_num(row, "AST"),
                fg3_pct=_num(row, "FG3_PCT"),
                fg3a=_num(row, "FG3A"),
                ts_pct=_num(adv, "TS_PCT"),
                usage_pct=_num(adv, "USG_PCT"),
            )
        )
    return lines


def fetch_season_stats(season: int) -> list[StatLine]:
    """One Base and one Advanced dashboard call for the season."""
    label = season_label(season)
    base = leaguedashplayerstats.LeagueDashPlayerStats(
        season=label, per_mode_detailed="PerGame", timeout=_TIMEOUT_S
    ).get_normalized_dict()["LeagueDashPlayerStats"]
    time.sleep(_REQUEST_DELAY_S)
    advanced = leaguedashplayerstats.LeagueDashPlayerStats(
        season=label,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced",
        timeout=_TIMEOUT_S,
    ).get_normalized_dict()["LeagueDashPlayerStats"]
    time.sleep(_REQUEST_DELAY_S)
    lines = rows_to_stat_lines(base, advanced, season=season)
    logger.info("nba_stats.season_fetched", season=season, players=len(lines))
    return lines


def fetch_rosters(season: int, team_nba_ids: dict[str, int]) -> list[RosterEntry]:
    """One roster call per team. ``team_nba_ids`` maps team abbreviation to NBA team id."""
    label = season_label(season)
    entries: list[RosterEntry] = []
    for abbr, nba_team_id in sorted(team_nba_ids.items()):
        rows = commonteamroster.CommonTeamRoster(
            team_id=nba_team_id, season=label, timeout=_TIMEOUT_S
        ).get_normalized_dict()["CommonTeamRoster"]
        for row in rows:
            entries.append(
                RosterEntry(
                    nba_player_id=int(row["PLAYER_ID"]),
                    name=str(row["PLAYER"]),
                    team_abbr=abbr,
                    position=(str(row["POSITION"]) or None) if row.get("POSITION") else None,
                    jersey=(str(row["NUM"]) or None) if row.get("NUM") else None,
                    age=float(row.get("AGE") or 0.0),
                    experience=parse_experience(str(row.get("EXP", ""))),
                )
            )
        time.sleep(_REQUEST_DELAY_S)
    logger.info("nba_stats.rosters_fetched", season=season, players=len(entries))
    return entries
```

- [ ] **Step 5: Run tests and the gates**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_nba_stats.py -p no:warnings`
Expected: PASS (6 tests)

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock etl/providers/ tests/etl/test_nba_stats.py
git commit -m "Add nba_api provider wrapper for rosters and season stats"
```

---

## Task 5: The sync job

**Files:**
- Create: `etl/jobs/sync_rosters.py`
- Test: `tests/etl/test_sync_rosters.py`

**Interfaces:**
- Consumes: `match_players`, `RosterEntry`, `StatLine`, `SeasonLine`, `Insight`, `regression_signal`, `breakout_signal`, `fetch_rosters`, `fetch_season_stats`.
- Produces: `async def run(session: AsyncSession, *, roster_season: int, stat_seasons: list[int], rosters: list[RosterEntry], stat_lines: list[StatLine]) -> JobSummary`. Fetching happens in `main()`, so tests inject data without touching the network.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the roster sync job."""

import pytest
from sqlalchemy import select

from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.models.team import Team
from etl.jobs import sync_rosters
from etl.providers.nba_stats import RosterEntry, StatLine


def roster(nba_id: int, name: str, abbr: str, age: float = 22.0, exp: int = 2) -> RosterEntry:
    return RosterEntry(
        nba_player_id=nba_id,
        name=name,
        team_abbr=abbr,
        position="G",
        jersey="1",
        age=age,
        experience=exp,
    )


def stat(
    nba_id: int,
    name: str,
    abbr: str,
    season: int,
    *,
    minutes: float = 30.0,
    points: float = 15.0,
    usage: float = 0.22,
    fg3_pct: float = 0.35,
    fg3a: float = 5.0,
    gp: int = 70,
) -> StatLine:
    return StatLine(
        nba_player_id=nba_id,
        name=name,
        team_abbr=abbr,
        season=season,
        games_played=gp,
        minutes=minutes,
        points=points,
        rebounds=4.0,
        assists=3.0,
        fg3_pct=fg3_pct,
        fg3a=fg3a,
        ts_pct=0.56,
        usage_pct=usage,
    )


@pytest.fixture
async def seeded(session):
    team = Team(
        external_id=1,
        abbreviation="LAL",
        name="Lakers",
        full_name="Los Angeles Lakers",
        city="Los Angeles",
        conference="West",
        division="Pacific",
    )
    session.add(team)
    await session.flush()
    player = Player(external_id=900, first_name="Luka", last_name="Doncic", team_id=team.id)
    session.add(player)
    await session.commit()
    return team, player


async def test_run_marks_matched_players_as_rostered(session, seeded):
    team, player = seeded
    summary = await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(1, "Luka Doncic", "LAL")],
        stat_lines=[stat(1, "Luka Doncic", "LAL", 2025)],
    )
    await session.refresh(player)
    assert player.roster_season == 2026
    assert player.nba_player_id == 1
    assert summary.rows_processed == 1


async def test_run_inserts_unmatched_roster_players(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(2, "Yang Hansen", "LAL")],
        stat_lines=[],
    )
    rows = (
        await session.execute(select(Player).where(Player.nba_player_id == 2))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].first_name == "Yang"
    assert rows[0].last_name == "Hansen"
    assert rows[0].roster_season == 2026


async def test_run_clears_roster_season_for_players_no_longer_rostered(session, seeded):
    team, player = seeded
    player.roster_season = 2026
    await session.commit()

    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(3, "Someone Else", "LAL")],
        stat_lines=[],
    )
    await session.refresh(player)
    assert player.roster_season is None


async def test_run_stores_season_stats(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2024, 2025],
        rosters=[roster(1, "Luka Doncic", "LAL")],
        stat_lines=[stat(1, "Luka Doncic", "LAL", 2024), stat(1, "Luka Doncic", "LAL", 2025)],
    )
    rows = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert {row.season for row in rows} == {2024, 2025}


async def test_run_writes_breakout_insight(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2024, 2025],
        rosters=[roster(1, "Luka Doncic", "LAL", age=22.0, exp=2)],
        stat_lines=[
            stat(1, "Luka Doncic", "LAL", 2024, minutes=18.0, points=6.0, usage=0.16),
            stat(1, "Luka Doncic", "LAL", 2025, minutes=28.0, points=15.0, usage=0.23),
        ],
    )
    rows = (await session.execute(select(PlayerInsight))).scalars().all()
    assert [row.kind for row in rows] == ["breakout"]
    assert rows[0].detail


async def test_run_is_idempotent(session, seeded):
    args = dict(
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[roster(1, "Luka Doncic", "LAL")],
        stat_lines=[stat(1, "Luka Doncic", "LAL", 2025)],
    )
    await sync_rosters.run(session, **args)
    await sync_rosters.run(session, **args)
    stats = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert len(stats) == 1


async def test_run_ignores_stats_for_unrostered_players(session, seeded):
    await sync_rosters.run(
        session,
        roster_season=2026,
        stat_seasons=[2025],
        rosters=[],
        stat_lines=[stat(99, "Nobody Here", "LAL", 2025)],
    )
    stats = (await session.execute(select(PlayerSeasonStat))).scalars().all()
    assert stats == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_sync_rosters.py -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'sync_rosters'`

- [ ] **Step 3: Write the implementation**

```python
"""Sync current rosters, player season stats and derived insights from nba_api.

Local-only: the NBA blocks datacenter IPs, so this never runs in CI or on the deployed host
(docs/superpowers/specs/2026-08-30-current-rosters-and-player-insights-design.md). Run it by hand
when rosters change.

Run as: ``python -m etl.jobs.sync_rosters``
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.player_season_stat import PlayerSeasonStat
from backend.app.models.team import Team
from etl.core.names import match_players
from etl.core.summary import JobSummary
from etl.core.upsert import upsert
from etl.providers.nba_stats import RosterEntry, StatLine, fetch_rosters, fetch_season_stats
from ml.pipeline.player_signals import SeasonLine, breakout_signal, regression_signal

logger = get_logger("etl.sync_rosters")

DEFAULT_ROSTER_SEASON = 2026
DEFAULT_STAT_SEASONS = [2022, 2023, 2024, 2025]

STAT_UPDATE_COLS = [
    "team_id",
    "games_played",
    "minutes",
    "points",
    "rebounds",
    "assists",
    "fg3_pct",
    "fg3a",
    "ts_pct",
    "usage_pct",
]
INSIGHT_UPDATE_COLS = ["score", "detail", "generated_at"]


def _split_name(name: str) -> tuple[str, str]:
    parts = name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


async def run(
    session: AsyncSession,
    *,
    roster_season: int,
    stat_seasons: list[int],
    rosters: list[RosterEntry],
    stat_lines: list[StatLine],
) -> JobSummary:
    summary = JobSummary(job="sync_rosters")

    teams = (await session.execute(select(Team))).scalars().all()
    team_id_by_abbr = {team.abbreviation: team.id for team in teams}

    db_players = (await session.execute(select(Player))).scalars().all()
    db_tuples = [
        (
            player.id,
            f"{player.first_name} {player.last_name}",
            next(
                (abbr for abbr, tid in team_id_by_abbr.items() if tid == player.team_id),
                "",
            ),
        )
        for player in db_players
    ]
    nba_tuples = [(entry.nba_player_id, entry.name, entry.team_abbr) for entry in rosters]
    matched, unmatched = match_players(nba_tuples, db_tuples)

    # Insert the players no pass could pair, keyed by NBA id so later syncs join directly.
    entry_by_nba_id = {entry.nba_player_id: entry for entry in rosters}
    for nba_id in unmatched:
        entry = entry_by_nba_id[nba_id]
        first, last = _split_name(entry.name)
        player = Player(
            external_id=-nba_id,  # negative keeps it clear of balldontlie's id space
            first_name=first,
            last_name=last,
            position=entry.position,
            jersey_number=entry.jersey,
            team_id=team_id_by_abbr.get(entry.team_abbr),
            nba_player_id=nba_id,
            roster_season=roster_season,
        )
        session.add(player)
        await session.flush()
        matched[nba_id] = player.id
    if unmatched:
        logger.info("sync_rosters.inserted_unmatched", count=len(unmatched))

    # Anyone previously rostered for this season who is no longer on a roster is cleared first,
    # so a traded or waived player does not linger on a team page.
    await session.execute(
        update(Player)
        .where(Player.roster_season == roster_season)
        .values(roster_season=None)
    )
    for nba_id, player_id in matched.items():
        entry = entry_by_nba_id[nba_id]
        await session.execute(
            update(Player)
            .where(Player.id == player_id)
            .values(
                nba_player_id=nba_id,
                roster_season=roster_season,
                team_id=team_id_by_abbr.get(entry.team_abbr),
                position=entry.position,
                jersey_number=entry.jersey,
            )
        )
    summary.rows_processed = len(matched)

    # Season stats, restricted to rostered players.
    stat_rows = []
    for line in stat_lines:
        player_id = matched.get(line.nba_player_id)
        if player_id is None or line.season not in stat_seasons:
            continue
        stat_rows.append(
            {
                "player_id": player_id,
                "season": line.season,
                "team_id": team_id_by_abbr.get(line.team_abbr),
                "games_played": line.games_played,
                "minutes": line.minutes,
                "points": line.points,
                "rebounds": line.rebounds,
                "assists": line.assists,
                "fg3_pct": line.fg3_pct,
                "fg3a": line.fg3a,
                "ts_pct": line.ts_pct,
                "usage_pct": line.usage_pct,
            }
        )
    if stat_rows:
        await upsert(
            session,
            PlayerSeasonStat,
            stat_rows,
            conflict_cols=["player_id", "season"],
            update_cols=STAT_UPDATE_COLS,
        )

    # Recompute insights from scratch: a flag that no longer holds must disappear.
    insight_season = max(stat_seasons)
    await session.execute(delete(PlayerInsight).where(PlayerInsight.season == insight_season))

    lines_by_player: dict[int, list[SeasonLine]] = {}
    for row in stat_rows:
        lines_by_player.setdefault(int(row["player_id"]), []).append(
            SeasonLine(
                season=int(row["season"]),
                games_played=int(row["games_played"]),
                minutes=float(row["minutes"]),
                points=float(row["points"]),
                rebounds=float(row["rebounds"]),
                assists=float(row["assists"]),
                fg3_pct=float(row["fg3_pct"]),
                fg3a=float(row["fg3a"]),
                ts_pct=float(row["ts_pct"]),
                usage_pct=float(row["usage_pct"]),
            )
        )

    now = datetime.now(UTC)
    insight_rows = []
    for nba_id, player_id in matched.items():
        lines = lines_by_player.get(player_id, [])
        entry = entry_by_nba_id[nba_id]
        for insight in (
            regression_signal(lines),
            breakout_signal(lines, age=entry.age, experience=entry.experience),
        ):
            if insight is None:
                continue
            insight_rows.append(
                {
                    "player_id": player_id,
                    "season": insight_season,
                    "kind": insight.kind,
                    "score": insight.score,
                    "detail": insight.detail,
                    "generated_at": now,
                }
            )
    if insight_rows:
        await upsert(
            session,
            PlayerInsight,
            insight_rows,
            conflict_cols=["player_id", "season", "kind"],
            update_cols=INSIGHT_UPDATE_COLS,
        )

    await session.commit()
    logger.info(
        "sync_rosters.done",
        rostered=len(matched),
        stats=len(stat_rows),
        insights=len(insight_rows),
    )
    return summary


async def main() -> None:
    from backend.app.db.session import async_session

    async with async_session() as session:
        teams = (await session.execute(select(Team))).scalars().all()
        # nba_api's team ids are stable and unrelated to ours; look them up from its static data.
        from nba_api.stats.static import teams as nba_teams

        nba_by_abbr = {t["abbreviation"]: int(t["id"]) for t in nba_teams.get_teams()}
        team_nba_ids = {
            team.abbreviation: nba_by_abbr[team.abbreviation]
            for team in teams
            if team.abbreviation in nba_by_abbr
        }

        rosters = fetch_rosters(DEFAULT_ROSTER_SEASON, team_nba_ids)
        stat_lines: list[StatLine] = []
        for season in DEFAULT_STAT_SEASONS:
            stat_lines.extend(fetch_season_stats(season))

        summary = await run(
            session,
            roster_season=DEFAULT_ROSTER_SEASON,
            stat_seasons=DEFAULT_STAT_SEASONS,
            rosters=rosters,
            stat_lines=stat_lines,
        )
    logger.info("etl.job.summary", **summary.as_dict())


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests and the gates**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/etl/test_sync_rosters.py -p no:warnings`
Expected: PASS (7 tests)

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml`
Expected: all clean

- [ ] **Step 5: Commit**

```bash
git add etl/jobs/sync_rosters.py tests/etl/test_sync_rosters.py
git commit -m "Add sync_rosters job for current rosters, stats and insights"
```

---

## Task 6: API

**Files:**
- Modify: `backend/app/schemas/player.py`, `backend/app/services/players.py`, `backend/app/api/v1/players.py`, `backend/app/core/cache.py`
- Create: `backend/app/schemas/player_insight.py`, `backend/app/services/player_insights.py`
- Test: `tests/backend/test_player_insights_api.py`

**Interfaces:**
- Consumes: `PlayerInsight`, `PlayerSeasonStat`, `Player.roster_season`.
- Produces: `GET /api/v1/players?active=true`; `GET /api/v1/players/insights?season=<int>&kind=<breakout|regression>`; `PlayerInsightOut` with `player_id, first_name, last_name, team_id, team_abbreviation, season, kind, score, detail`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the player insights endpoint and the active filter."""

import pytest

from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.team import Team


@pytest.fixture
async def seeded(session):
    team = Team(
        external_id=1,
        abbreviation="LAL",
        name="Lakers",
        full_name="Los Angeles Lakers",
        city="Los Angeles",
        conference="West",
        division="Pacific",
    )
    session.add(team)
    await session.flush()
    active = Player(
        external_id=1,
        first_name="Luka",
        last_name="Doncic",
        team_id=team.id,
        roster_season=2026,
    )
    retired = Player(external_id=2, first_name="Kareem", last_name="Abdul-Jabbar", team_id=team.id)
    session.add_all([active, retired])
    await session.flush()
    session.add(
        PlayerInsight(
            player_id=active.id,
            season=2025,
            kind="breakout",
            score=3.2,
            detail="18.0 to 28.0 minutes",
        )
    )
    await session.commit()
    return active, retired


async def test_players_active_filter_excludes_historical(client, seeded):
    response = await client.get("/api/v1/players?active=true")
    assert response.status_code == 200
    names = [row["last_name"] for row in response.json()["data"]]
    assert names == ["Doncic"]


async def test_players_without_filter_returns_everyone(client, seeded):
    response = await client.get("/api/v1/players")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 2


async def test_insights_route_is_not_shadowed_by_the_id_route(client, seeded):
    # Declared after /players/{player_id} this returns 422 as FastAPI tries to parse "insights".
    response = await client.get("/api/v1/players/insights?season=2025")
    assert response.status_code == 200


async def test_insights_returns_supporting_detail(client, seeded):
    response = await client.get("/api/v1/players/insights?season=2025")
    row = response.json()["data"][0]
    assert row["kind"] == "breakout"
    assert row["detail"] == "18.0 to 28.0 minutes"
    assert row["team_abbreviation"] == "LAL"
    assert row["last_name"] == "Doncic"


async def test_insights_filters_by_kind(client, seeded):
    response = await client.get("/api/v1/players/insights?season=2025&kind=regression")
    assert response.json()["data"] == []


async def test_insights_filters_by_season(client, seeded):
    response = await client.get("/api/v1/players/insights?season=2024")
    assert response.json()["data"] == []


async def test_get_player_by_id_still_works(client, seeded):
    active, _ = seeded
    response = await client.get(f"/api/v1/players/{active.id}")
    assert response.status_code == 200
    assert response.json()["data"]["last_name"] == "Doncic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/backend/test_player_insights_api.py -p no:warnings`
Expected: FAIL — the `active` parameter is ignored and `/players/insights` returns 422

- [ ] **Step 3: Add the schema**

Create `backend/app/schemas/player_insight.py`:

```python
"""Player insight response schema."""

from pydantic import BaseModel, ConfigDict


class PlayerInsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    first_name: str
    last_name: str
    team_id: int | None
    team_abbreviation: str | None
    season: int
    kind: str
    score: float
    detail: str
```

Add `roster_season` to `PlayerOut` in `backend/app/schemas/player.py`:

```python
    roster_season: int | None = None
```

- [ ] **Step 4: Add the service**

Create `backend/app/services/player_insights.py`:

```python
"""Player insight queries."""

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import Pagination
from backend.app.models.player import Player
from backend.app.models.player_insight import PlayerInsight
from backend.app.models.team import Team
from backend.app.services.common import total_count


def _base(season: int, kind: str | None) -> Select[tuple[PlayerInsight, Player, Team]]:
    stmt = (
        select(PlayerInsight, Player, Team)
        .join(Player, Player.id == PlayerInsight.player_id)
        .join(Team, Team.id == Player.team_id, isouter=True)
        .where(PlayerInsight.season == season)
        # Only players currently in the league are ever surfaced.
        .where(Player.roster_season.is_not(None))
    )
    if kind is not None:
        stmt = stmt.where(PlayerInsight.kind == kind)
    return stmt


async def list_insights(
    session: AsyncSession, *, page: Pagination, season: int, kind: str | None = None
) -> tuple[list[dict[str, object]], int]:
    stmt = _base(season, kind)
    total = await total_count(session, stmt)
    # Strongest signal first, regardless of sign — a big drop is as interesting as a big rise.
    stmt = (
        stmt.order_by(PlayerInsight.score.desc()).limit(page.limit).offset(page.offset)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "player_id": insight.player_id,
            "first_name": player.first_name,
            "last_name": player.last_name,
            "team_id": player.team_id,
            "team_abbreviation": team.abbreviation if team is not None else None,
            "season": insight.season,
            "kind": insight.kind,
            "score": insight.score,
            "detail": insight.detail,
        }
        for insight, player, team in rows
    ], total
```

- [ ] **Step 5: Add the `active` filter to the players service**

In `backend/app/services/players.py`, change the `list_players` signature and body:

```python
async def list_players(
    session: AsyncSession,
    *,
    page: Pagination,
    team_id: int | None = None,
    search: str | None = None,
    active: bool | None = None,
) -> tuple[list[Player], int]:
    stmt = select(Player)
    if team_id is not None:
        stmt = stmt.where(Player.team_id == team_id)
    if search:
        stmt = stmt.where(Player.last_name.ilike(f"%{search}%"))
    if active:
        stmt = stmt.where(Player.roster_season.is_not(None))
    total = await total_count(session, stmt)
    stmt = stmt.order_by(Player.last_name, Player.first_name).limit(page.limit).offset(page.offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total
```

- [ ] **Step 6: Wire the routes, insights first**

In `backend/app/api/v1/players.py`, add the `active` query parameter to `list_players`, then insert the insights route **above** `get_player`:

```python
@router.get("/insights", response_model=PagedEnvelope[PlayerInsightOut])
async def list_player_insights(
    session: SessionDep,
    page: PaginationDep,
    season: Annotated[int, Query()],
    kind: Annotated[str | None, Query(pattern="^(breakout|regression)$")] = None,
) -> PagedEnvelope[PlayerInsightOut]:
    items, total = await player_insights_service.list_insights(
        session, page=page, season=season, kind=kind
    )
    return PagedEnvelope[PlayerInsightOut](
        data=[PlayerInsightOut.model_validate(row) for row in items],
        meta=build_meta(total, page, len(items)),
    )
```

Add the imports:

```python
from backend.app.schemas.player_insight import PlayerInsightOut
from backend.app.services import player_insights as player_insights_service
```

And thread `active` through the list route:

```python
    active: Annotated[bool | None, Query()] = None,
```
passing `active=active` into `players_service.list_players`.

**This route must be declared before `@router.get("/{player_id}")`.** FastAPI matches in
declaration order; below it, `/players/insights` is routed to the id handler and fails to parse
"insights" as an integer.

- [ ] **Step 7: Run tests and the gates**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest tests/backend -p no:warnings`
Expected: PASS, including the 7 new tests

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml`
Expected: all clean

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/ backend/app/services/ backend/app/api/ tests/backend/test_player_insights_api.py
git commit -m "Serve player insights and an active-roster filter"
```

---

## Task 7: Players page

**Files:**
- Create: `frontend/src/hooks/usePlayerInsights.ts`, `frontend/src/pages/Players.test.tsx`
- Modify: `frontend/src/api/types.ts`, `frontend/src/hooks/usePlayers.ts`, `frontend/src/pages/Players.tsx`

**Interfaces:**
- Consumes: `GET /players?active=true`, `GET /players/insights?season&kind`.
- Produces: `usePlayerInsights({season, kind})` returning `Paged<PlayerInsight>`.

- [ ] **Step 1: Add the types**

In `frontend/src/api/types.ts`:

```ts
export interface PlayerInsight {
  player_id: number;
  first_name: string;
  last_name: string;
  team_id: number | null;
  team_abbreviation: string | null;
  season: number;
  kind: "breakout" | "regression";
  score: number;
  detail: string;
}
```

Add `roster_season: number | null;` to the existing `Player` interface.

- [ ] **Step 2: Add the hook**

Create `frontend/src/hooks/usePlayerInsights.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

import { apiGet, type Paged } from "../api/client";
import type { PlayerInsight } from "../api/types";

export interface PlayerInsightFilters {
  season: number;
  kind?: "breakout" | "regression";
}

export function usePlayerInsights({ season, kind }: PlayerInsightFilters) {
  return useQuery({
    queryKey: ["player-insights", season, kind],
    queryFn: () =>
      apiGet<Paged<PlayerInsight>>("/players/insights", { season, kind, limit: 50 }),
  });
}
```

- [ ] **Step 3: Add `active` to `usePlayers`**

In `frontend/src/hooks/usePlayers.ts`, add `active?: boolean;` to `PlayerFilters`. The existing
`queryFn` already spreads filters into the query string, so no other change is needed.

- [ ] **Step 4: Write the failing test**

Create `frontend/src/pages/Players.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Players from "./Players";

vi.mock("../hooks/usePlayers", () => ({
  usePlayers: () => ({
    data: {
      data: [
        {
          id: 1,
          first_name: "Luka",
          last_name: "Doncic",
          position: "G",
          team_id: 1,
          roster_season: 2026,
        },
      ],
      meta: { total: 1, limit: 25, offset: 0, has_more: false },
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/usePlayerInsights", () => ({
  usePlayerInsights: ({ kind }: { kind?: string }) => ({
    data: {
      data:
        kind === "breakout"
          ? [
              {
                player_id: 1,
                first_name: "Luka",
                last_name: "Doncic",
                team_id: 1,
                team_abbreviation: "LAL",
                season: 2025,
                kind: "breakout",
                score: 3.2,
                detail: "18.0 to 28.0 minutes",
              },
            ]
          : [],
      meta: { total: 1, limit: 50, offset: 0, has_more: false },
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/useTeams", () => ({
  useTeams: () => ({
    data: {
      data: [{ id: 1, abbreviation: "LAL", full_name: "Los Angeles Lakers" }],
      meta: { total: 1, limit: 100, offset: 0, has_more: false },
    },
    isLoading: false,
    isError: false,
  }),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Players />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Players", () => {
  it("renders the player table", () => {
    renderPage();
    expect(screen.getAllByText(/Doncic/).length).toBeGreaterThan(0);
  });

  it("shows a breakout candidate with its supporting detail", () => {
    renderPage();
    expect(screen.getByText("18.0 to 28.0 minutes")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd frontend && npm run test -- Players`
Expected: FAIL — `usePlayerInsights` is not used by the page yet, so the detail text is absent

- [ ] **Step 6: Update the Players page**

In `frontend/src/pages/Players.tsx`:

1. Import `usePlayerInsights` and `useState`.
2. Add `const [activeOnly, setActiveOnly] = useState(true);` and pass `active: activeOnly` to `usePlayers`.
3. Call `const breakouts = usePlayerInsights({ season: 2025, kind: "breakout" });` and
   `const regressions = usePlayerInsights({ season: 2025, kind: "regression" });`
4. Above the table, render the insight section:

```tsx
{([
  ["Primed to break out", breakouts] as const,
  ["Regression candidates", regressions] as const,
]).map(([title, query]) => (
  <Card key={title}>
    <SectionTitle>{title}</SectionTitle>
    <QueryState query={query}>
      {(page) =>
        page.data.length === 0 ? (
          <EmptyState>No candidates for this season.</EmptyState>
        ) : (
          <ul className="divide-y divide-border">
            {page.data.slice(0, 10).map((insight) => (
              <li key={`${insight.player_id}-${insight.kind}`} className="py-2">
                <div className="flex items-center gap-2">
                  <TeamMark abbr={insight.team_abbreviation ?? ""} />
                  <span className="font-semibold">
                    {insight.first_name} {insight.last_name}
                  </span>
                </div>
                <p className="text-sm text-muted">{insight.detail}</p>
              </li>
            ))}
          </ul>
        )
      }
    </QueryState>
  </Card>
))}
```

Match the surrounding file's existing prop names for `TeamMark`, `QueryState` and `EmptyState`;
if they differ, follow the file rather than this snippet.
5. Add a toggle above the search input reading "Current players" / "All time", driven by
   `activeOnly`, so the historical index remains reachable.

Follow the existing page structure: `PageHeader` with `eyebrow`, `SectionTitle` for each block,
`Card` wrappers, and `QueryState` for loading and error handling.

- [ ] **Step 7: Run tests and the gates**

Run: `cd frontend && npm run test && npm run lint && npm run typecheck && npm run build`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "Show current players and breakout/regression candidates"
```

---

## Task 8: Team detail roster

**Files:**
- Modify: `frontend/src/pages/TeamDetail.tsx`

**Interfaces:**
- Consumes: `usePlayers({team_id, active: true})`, `usePlayerInsights({season: 2025})`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/TeamDetail.test.tsx` using the same structure as `Players.test.tsx` from
Task 7: a `QueryClientProvider` wrapped in `MemoryRouter`, with `vi.mock` for `useTeam`, `useGames`,
`useStandings`, `useTeams`, `usePlayers` (returning one player with `id: 1`, `roster_season: 2026`)
and `usePlayerInsights` (returning one `breakout` row with `player_id: 1`). Then assert:

```tsx
it("labels a flagged player on the roster", () => {
  renderPage();
  expect(screen.getByText(/breakout/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- TeamDetail`
Expected: FAIL — no badge is rendered

- [ ] **Step 3: Update the page**

In `frontend/src/pages/TeamDetail.tsx`:

1. Pass `active: true` to the existing `usePlayers({ team_id: id })` call so the roster shows only
   current players.
2. Call `usePlayerInsights({ season: 2025 })` and build a `Map<number, PlayerInsight>` keyed by
   `player_id`.
3. In the roster table, render a badge beside any player carrying an insight:

```tsx
{insightByPlayer.get(player.id) ? (
  <span
    title={insightByPlayer.get(player.id)!.detail}
    className={
      insightByPlayer.get(player.id)!.kind === "breakout"
        ? "ml-2 rounded px-1.5 py-0.5 text-xs font-semibold text-win ring-1 ring-win/40"
        : "ml-2 rounded px-1.5 py-0.5 text-xs font-semibold text-loss ring-1 ring-loss/40"
    }
  >
    {insightByPlayer.get(player.id)!.kind}
  </span>
) : null}
```

The `title` attribute puts the supporting numbers on hover without widening the table.
4. Update the roster section's subtitle from the all-time framing to "Current roster".

- [ ] **Step 4: Run tests and the gates**

Run: `cd frontend && npm run test && npm run lint && npm run typecheck && npm run build`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/TeamDetail.tsx frontend/src/pages/TeamDetail.test.tsx
git commit -m "Show current roster with insight badges on team detail"
```

---

## Task 9: Load the data and verify

**Files:** none — this task runs the job and confirms the result.

- [ ] **Step 1: Apply the migration locally**

```bash
docker compose -f docker/docker-compose.yml up -d
PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run alembic -c backend/alembic.ini upgrade head
```

- [ ] **Step 2: Run the sync job**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run python -m etl.jobs.sync_rosters`

Expected: roughly 38 requests over about a minute, ending with a `sync_rosters.done` log line
reporting rostered, stats and insights counts.

- [ ] **Step 3: Verify the data**

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U nba -d nba -c "select count(*) filter (where roster_season=2026) rostered, count(*) total from players;"
docker compose -f docker/docker-compose.yml exec -T db psql -U nba -d nba -c "select kind, count(*) from player_insights group by kind;"
```

Expected: roughly 500-550 rostered players out of ~5,800 total, and both `breakout` and
`regression` present.

**Sanity check the thresholds.** If either kind returns more than about 60 players the signal is
too loose to be interesting, and if it returns fewer than about 5 it is too tight. Report the
counts rather than silently adjusting — `REGRESSION_THRESHOLD_PCT` is an unvalidated judgement call
and tuning it is a decision for the project owner.

- [ ] **Step 4: Verify in the browser**

```bash
docker compose -f docker/docker-compose.yml exec -T redis redis-cli FLUSHALL
docker compose -f docker/docker-compose.yml up -d --build backend frontend
```

Open `http://localhost:5173/players` and a team page. Confirm the roster shows current players
only, that no retired player appears, and that insight badges carry their supporting numbers.

- [ ] **Step 5: Run the full gate set**

Run: `PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run ruff check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run black --check . && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run mypy backend etl ml && PYTHONPATH="C:/Users/Cooper/cld_powers" python -m uv run pytest -p no:warnings --cov=backend --cov-fail-under=80`
Expected: all clean

Run: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`
Expected: all pass

- [ ] **Step 6: Commit any documentation updates**

Update `README.md` to mention that rosters and player stats come from `nba_api` via a local-only
job, and note in `docs/decisions.md` that D-006's "no player data" constraint is now partially
lifted for season aggregates.

```bash
git add README.md docs/decisions.md
git commit -m "Document the nba_api roster and stats source"
```

---

## Deployment note

The migration must reach `main` **before** it is applied to the production database. Applying it
from this branch would stamp `alembic_version` with a revision the deployed image cannot resolve,
crash-looping the API — this happened on 2026-08-27 and is recorded in `docs/deployment.md`. Merge
first, let the deploy run the migration, then load the data into the cloud database.
