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


def test_regression_requires_baseline_volume() -> None:
    # Prior season has 70 games x 1.0 attempts = 70 attempts, below the 200 floor.
    thin = [line(2024, fg3a=1.0, fg3_pct=0.100), line(2025, fg3_pct=0.430)]
    assert regression_signal(thin) is None


def test_regression_accepts_a_well_established_baseline() -> None:
    # Prior season has 70 games x 5.0 attempts = 350 attempts, clearing the floor.
    solid = [line(2024, fg3a=5.0, fg3_pct=0.330), line(2025, fg3_pct=0.430)]
    insight = regression_signal(solid)
    assert insight is not None
    assert insight.score > 0


def test_regression_baseline_volume_accumulates_across_seasons() -> None:
    # Two prior seasons at 140 attempts each clear the 200 floor together but not individually.
    spread = [
        line(2023, fg3a=2.0, fg3_pct=0.330),
        line(2024, fg3a=2.0, fg3_pct=0.330),
        line(2025, fg3_pct=0.430),
    ]
    assert regression_signal(spread) is not None
