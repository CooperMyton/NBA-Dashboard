"""Breakout and regression signals from player season lines.

Two deliberately transparent signals, each reporting the numbers that produced it so the UI can
justify every flag (see design spec: 2026-08-30-current-rosters-and-player-insights-design.md).

Regression compares a player's most recent shooting to their own volume-weighted baseline —
shooting far above your established rate tends not to hold. Breakout looks for a young player
whose minutes, usage and per-36 production are all rising.
"""

from dataclasses import dataclass

# A shooting swing of four percentage points is large enough to be worth surfacing.
REGRESSION_THRESHOLD_PCT = 4.0
MIN_GAMES = 20
MIN_THREE_ATTEMPTS = 100
# The baseline needs real volume behind it or the comparison is noise: a player with a handful of
# career attempts produces a wild baseline and swamps the genuinely interesting cases.
MIN_BASELINE_THREE_ATTEMPTS = 200
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
    """Flag a player shooting far from their own volume-weighted baseline.

    Both the recent season and the baseline must clear a volume floor: the recent season needs
    MIN_GAMES and MIN_THREE_ATTEMPTS, and the prior-season baseline needs
    MIN_BASELINE_THREE_ATTEMPTS, or the comparison is too noisy to be meaningful.
    """
    ordered = _sorted(lines)
    if len(ordered) < 2:
        return None

    recent, prior = ordered[-1], ordered[:-1]
    if recent.games_played < MIN_GAMES or recent.three_attempts < MIN_THREE_ATTEMPTS:
        return None

    weight = sum(line.three_attempts for line in prior)
    if weight <= 0:
        return None
    if weight < MIN_BASELINE_THREE_ATTEMPTS:
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
