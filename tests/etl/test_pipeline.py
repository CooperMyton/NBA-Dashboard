"""End-to-end test of the nightly pipeline runner against SQLite + fakeredis."""

from fakeredis import FakeAsyncRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.base import Base
from backend.app.models.game import Game
from backend.app.models.player import Player
from backend.app.models.standing import Standing
from backend.app.models.team import Team
from backend.app.models.team_stat import TeamStat
from etl.pipeline import run_pipeline
from tests.etl.conftest import load_fixture
from tests.etl.fake_client import FakeClient


async def _count(session: AsyncSession, model: type[Base]) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_run_pipeline_populates_tables_and_invalidates_cache(session: AsyncSession) -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    await redis.set("standings:2023", "stale")
    await redis.set("teams:all", "stale")
    await redis.set("predictions:next", "stale")

    client = FakeClient(
        teams=load_fixture("teams.json"),
        players=load_fixture("players.json"),
        games=load_fixture("games.json"),
    )
    # predictor=None -> predict_upcoming no-ops; the fixture games are already final.
    summaries = await run_pipeline(client, session, redis, seasons=[2023])  # type: ignore[arg-type]

    assert [s.job for s in summaries] == [
        "sync_teams",
        "sync_games",
        "derive_team_stats",
        "derive_standings",
        "settle_predictions",
        "predict_upcoming",
        "sync_players",
    ]
    assert all(s.errors == [] for s in summaries)

    assert await _count(session, Team) == 2
    assert await _count(session, Player) == 3
    assert await _count(session, Game) == 2
    assert await _count(session, TeamStat) == 4
    assert await _count(session, Standing) == 2

    # teams:/standings:/predictions: families all invalidated after the load.
    assert await redis.get("standings:2023") is None
    assert await redis.get("teams:all") is None
    assert await redis.get("predictions:next") is None
    await redis.aclose()
