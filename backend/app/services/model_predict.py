"""Inference service: predict P(home win) for a matchup using the active model.

Features come from the season's completed games (before the target date). Never retrains.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import not_found, service_unavailable
from backend.app.core.model import ActiveModel
from backend.app.models.team import Team
from ml.pipeline.collect import collect_games
from ml.pipeline.inference import features_for_matchup


async def predict_home_win(
    session: AsyncSession,
    active: ActiveModel,
    *,
    home_team_id: int,
    visitor_team_id: int,
    season: int,
    game_date: date | None = None,
) -> dict[str, Any]:
    predictor = active.predictor
    if predictor is None:
        raise service_unavailable("No active model is registered")

    known = set(
        (await session.execute(select(Team.id).where(Team.id.in_([home_team_id, visitor_team_id]))))
        .scalars()
        .all()
    )
    if home_team_id not in known or visitor_team_id not in known:
        raise not_found("Unknown team id")

    target_date = game_date or datetime.now(UTC).date()
    # Use all completed games so team Elo carries into the target season (even a new one).
    history = await collect_games(session)
    row = features_for_matchup(history, season, target_date, home_team_id, visitor_team_id)
    probability = predictor.predict_proba([row])[0]

    return {
        "home_team_id": home_team_id,
        "visitor_team_id": visitor_team_id,
        "season": season,
        "game_date": target_date,
        "model_version": predictor.model_version,
        "predicted_home_win_prob": probability,
        "predicted_home_win": probability >= 0.5,
    }
