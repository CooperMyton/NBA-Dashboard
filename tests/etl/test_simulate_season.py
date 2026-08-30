"""Tests for the season projection job."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.game import Game
from backend.app.models.season_projection import SeasonProjection
from backend.app.models.team import Team
from etl.jobs import simulate_season
from ml.pipeline.features import FEATURE_NAMES, build_training_data
from ml.pipeline.inference import Predictor
from ml.pipeline.train import train_model
from tests.ml.synth import synth_game_records

# resolve_play_in indexes seeds 7-10, so each conference needs at least ten teams.
_PER_CONFERENCE = 10


def _predictor() -> Predictor:
    features, labels, _ = build_training_data(synth_game_records())
    model = train_model(features, labels)
    return Predictor(model, version=1, feature_names=FEATURE_NAMES, model_version="test-model")


async def _seed_league(session: AsyncSession) -> list[int]:
    """Seed 20 teams and a 2026 round-robin schedule of unplayed games."""
    teams = []
    for index in range(_PER_CONFERENCE * 2):
        conference = "East" if index < _PER_CONFERENCE else "West"
        teams.append(
            Team(
                external_id=index + 1,
                abbreviation=f"T{index:02d}",
                name=f"Team {index}",
                full_name=f"City {index} Team {index}",
                city=f"City {index}",
                conference=conference,
                division="Atlantic" if conference == "East" else "Pacific",
            )
        )
    session.add_all(teams)
    await session.flush()

    team_ids = [t.id for t in teams]
    external = 9000
    for home in team_ids:
        for away in team_ids:
            if home == away:
                continue
            external += 1
            session.add(
                Game(
                    external_id=external,
                    season=2026,
                    game_date=date(2026, 10, 20) + timedelta(days=external % 150),
                    start_time=None,
                    status="2026-10-20T23:00:00Z",  # scheduled games carry their tip-off time
                    postseason=False,
                    period=None,
                    home_team_id=home,
                    visitor_team_id=away,
                    home_team_score=0,
                    visitor_team_score=0,
                )
            )
    await session.commit()
    return team_ids


async def test_no_active_model_is_a_no_op(session: AsyncSession) -> None:
    await _seed_league(session)
    summary = await simulate_season.run(session, None, season=2026, simulations=2)
    assert summary.rows_processed == 0
    rows = (await session.execute(select(SeasonProjection))).scalars().all()
    assert rows == []


async def test_no_schedule_is_a_no_op(session: AsyncSession) -> None:
    summary = await simulate_season.run(session, _predictor(), season=2026, simulations=2)
    assert summary.rows_processed == 0


async def test_writes_one_row_per_team_and_is_idempotent(session: AsyncSession) -> None:
    team_ids = await _seed_league(session)
    predictor = _predictor()

    summary = await simulate_season.run(session, predictor, season=2026, simulations=3, seed=1)
    assert summary.rows_processed == len(team_ids)

    rows = (await session.execute(select(SeasonProjection))).scalars().all()
    assert {r.team_id for r in rows} == set(team_ids)
    for row in rows:
        assert 0.0 <= row.make_playoffs_pct <= 100.0
        assert 0.0 <= row.win_title_pct <= 100.0
        assert row.simulations == 3
        assert row.season == 2026
        assert row.model_version == "test-model"

    # Title share is a probability distribution over the league.
    assert abs(sum(r.win_title_pct for r in rows) - 100.0) < 1e-6

    # Every game produces exactly one winner, so projected wins must sum to the game count.
    games = len(team_ids) * (len(team_ids) - 1)
    assert abs(sum(r.proj_wins for r in rows) - games) < 1e-6

    # Re-running must update in place, not duplicate.
    await simulate_season.run(session, predictor, season=2026, simulations=3, seed=1)
    again = (await session.execute(select(SeasonProjection))).scalars().all()
    assert len(again) == len(rows)
