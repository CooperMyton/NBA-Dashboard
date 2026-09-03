"""Backtest the season projection against completed seasons.

The live projection cannot be judged until a season ends, so this replays the pipeline on seasons
we already know the answer to. For each held-out season it trains a fresh model on strictly
earlier games, seeds team state from those games only, simulates the season's real schedule, and
compares projected win totals to actual ones. Nothing here touches the model registry or the
database tables the app reads.

Leakage matters: the active model was trained on data that includes the seasons being tested, so
reusing it would score the projection on games it has already seen. Retraining per season on
prior data only is what makes the number honest.

Two baselines make the error interpretable: predicting every team at the league mean (no skill),
and carrying forward last season's win total (persistence — the cheapest sensible forecast).

Run as: ``python -m ml.pipeline.backtest``
"""

import asyncio
import json
import os
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.models.game import Game
from backend.app.models.team import Team
from ml.pipeline.collect import collect_games
from ml.pipeline.features import FEATURE_NAMES, FeatureBuilder, GameRecord, build_training_data
from ml.pipeline.inference import Predictor
from ml.pipeline.run_training import MIN_GAMES
from ml.pipeline.simulation import ScheduledGame, run_simulations
from ml.pipeline.train import train_by_name

logger = get_logger("ml.backtest")

DEFAULT_SEASONS = [2024, 2025]
# Win-total error needs far less resolution than playoff odds do; 300 runs keeps a season to a
# couple of minutes while the simulation-to-simulation noise stays well under one win.
DEFAULT_SIMULATIONS = 300
ALGORITHM = "logistic_regression"


@dataclass(frozen=True)
class TeamError:
    team_id: int
    projected: float
    actual: int
    previous: int | None


@dataclass(frozen=True)
class BacktestResult:
    season: int
    teams: int
    simulations: int
    mae: float
    mae_mean_baseline: float
    mae_persistence_baseline: float | None
    rows: list[TeamError]


def evaluate_projection(
    projected: dict[int, float],
    actual: dict[int, int],
    previous: dict[int, int] | None = None,
    *,
    season: int = 0,
    simulations: int = 0,
) -> BacktestResult:
    """Score projected win totals against actual ones over the teams present in both."""
    team_ids = sorted(set(projected) & set(actual))
    if not team_ids:
        raise ValueError("no teams appear in both the projection and the actual results")

    previous = previous or {}
    rows = [
        TeamError(
            team_id=tid,
            projected=projected[tid],
            actual=actual[tid],
            previous=previous.get(tid),
        )
        for tid in team_ids
    ]

    mae = sum(abs(r.projected - r.actual) for r in rows) / len(rows)

    league_mean = sum(r.actual for r in rows) / len(rows)
    mae_mean = sum(abs(r.actual - league_mean) for r in rows) / len(rows)

    with_previous = [r for r in rows if r.previous is not None]
    mae_persistence = (
        sum(abs(r.actual - r.previous) for r in with_previous if r.previous is not None)
        / len(with_previous)
        if with_previous
        else None
    )

    return BacktestResult(
        season=season,
        teams=len(rows),
        simulations=simulations,
        mae=mae,
        mae_mean_baseline=mae_mean,
        mae_persistence_baseline=mae_persistence,
        rows=rows,
    )


def _chronological(games: list[GameRecord]) -> list[GameRecord]:
    return sorted(games, key=lambda g: (g.season, g.game_date, g.game_id))


async def _regular_season(session: AsyncSession, season: int) -> list[Game]:
    stmt = (
        select(Game)
        .where(Game.season == season)
        .where(Game.postseason.is_(False))
        .where(func.lower(Game.status) == "final")
        .order_by(Game.game_date, Game.id)
    )
    return list((await session.execute(stmt)).scalars().all())


def _win_totals(games: list[Game]) -> dict[int, int]:
    wins: dict[int, int] = {}
    for g in games:
        if g.home_team_score is None or g.visitor_team_score is None:
            continue
        winner = g.home_team_id if g.home_team_score > g.visitor_team_score else g.visitor_team_id
        wins[winner] = wins.get(winner, 0) + 1
        wins.setdefault(g.home_team_id, wins.get(g.home_team_id, 0))
        wins.setdefault(g.visitor_team_id, wins.get(g.visitor_team_id, 0))
    return wins


async def backtest_season(
    session: AsyncSession,
    season: int,
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = 0,
) -> BacktestResult | None:
    """Project one completed season from earlier data only and score it. None if too little data."""
    prior = _chronological([g for g in await collect_games(session) if g.season < season])
    if len(prior) < MIN_GAMES:
        logger.warning("ml.backtest.insufficient_prior_data", season=season, games=len(prior))
        return None

    features, labels, _ = build_training_data(prior)
    model = train_by_name(ALGORITHM, features, labels)
    predictor = Predictor(
        model, version=0, feature_names=FEATURE_NAMES, model_version=f"backtest-{season}"
    )

    builder = FeatureBuilder()
    for record in prior:
        builder.observe(record)

    played = await _regular_season(session, season)
    if not played:
        logger.warning("ml.backtest.no_games", season=season)
        return None
    schedule = [
        ScheduledGame(
            game_id=g.id,
            season=g.season,
            game_date=g.game_date,
            home_team_id=g.home_team_id,
            visitor_team_id=g.visitor_team_id,
        )
        for g in played
    ]
    conferences = {
        team.id: team.conference for team in (await session.execute(select(Team))).scalars().all()
    }

    projections = run_simulations(
        builder, schedule, predictor, conferences, simulations=simulations, seed=seed
    )
    projected = {p.team_id: p.proj_wins for p in projections}
    actual = _win_totals(played)
    previous = _win_totals(await _regular_season(session, season - 1))

    result = evaluate_projection(
        projected, actual, previous, season=season, simulations=simulations
    )
    logger.info(
        "ml.backtest.season",
        season=season,
        teams=result.teams,
        mae=round(result.mae, 2),
        mae_mean_baseline=round(result.mae_mean_baseline, 2),
        mae_persistence_baseline=(
            round(result.mae_persistence_baseline, 2)
            if result.mae_persistence_baseline is not None
            else None
        ),
        train_games=len(prior),
    )
    return result


def _parse_seasons(raw: str) -> list[int]:
    return [int(s) for s in raw.split(",") if s.strip()]


async def main() -> None:
    from backend.app.db.session import SessionLocal

    seasons = _parse_seasons(os.environ.get("BACKTEST_SEASONS", "")) or DEFAULT_SEASONS
    simulations = int(os.environ.get("BACKTEST_SIMULATIONS", DEFAULT_SIMULATIONS))

    results: list[BacktestResult] = []
    async with SessionLocal() as session:
        for season in seasons:
            result = await backtest_season(session, season, simulations=simulations)
            if result is not None:
                results.append(result)

    # Machine-readable summary on stdout so the numbers can be recorded without re-running.
    print(
        json.dumps([{k: v for k, v in asdict(r).items() if k != "rows"} for r in results], indent=2)
    )


if __name__ == "__main__":
    asyncio.run(main())
