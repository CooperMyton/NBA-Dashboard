"""API test harness: a seeded SQLite DB + fakeredis wired into the app via dependency overrides.

Env is set before importing the app so module-level settings/engine construction succeeds; the
real DB/Redis are never used (both dependencies are overridden).
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("BALLDONTLIE_API_KEY", "test")

import pathlib  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from datetime import UTC, date, datetime  # noqa: E402

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402
from fakeredis import FakeAsyncRedis  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.security import hash_api_key  # noqa: E402
from backend.app.models import Base  # noqa: E402
from backend.app.models.game import Game  # noqa: E402
from backend.app.models.model_prediction import ModelPrediction  # noqa: E402
from backend.app.models.player import Player  # noqa: E402
from backend.app.models.standing import Standing  # noqa: E402
from backend.app.models.team import Team  # noqa: E402
from backend.app.models.user import User  # noqa: E402

API_KEY = "test-api-key-abc123"


async def _seed(session: AsyncSession) -> None:
    bos = Team(
        external_id=1,
        abbreviation="BOS",
        name="Celtics",
        full_name="Boston Celtics",
        city="Boston",
        conference="East",
        division="Atlantic",
    )
    lal = Team(
        external_id=2,
        abbreviation="LAL",
        name="Lakers",
        full_name="Los Angeles Lakers",
        city="Los Angeles",
        conference="West",
        division="Pacific",
    )
    session.add_all([bos, lal])
    await session.flush()

    session.add_all(
        [
            Player(
                external_id=501,
                first_name="Jayson",
                last_name="Tatum",
                position="F",
                height=None,
                weight=None,
                jersey_number=None,
                college="Duke",
                country="USA",
                team_id=bos.id,
            ),
            Player(
                external_id=502,
                first_name="LeBron",
                last_name="James",
                position="F",
                height=None,
                weight=None,
                jersey_number=None,
                college=None,
                country="USA",
                team_id=lal.id,
            ),
        ]
    )

    game = Game(
        external_id=1001,
        season=2023,
        game_date=date(2024, 1, 15),
        start_time=datetime(2024, 1, 15, 23, 0, tzinfo=UTC),
        status="Final",
        postseason=False,
        period=4,
        home_team_id=bos.id,
        visitor_team_id=lal.id,
        home_team_score=110,
        visitor_team_score=104,
    )
    session.add(game)
    await session.flush()

    session.add_all(
        [
            Standing(
                season=2023,
                team_id=bos.id,
                wins=2,
                losses=0,
                win_pct=1.0,
                conference="East",
                conference_rank=1,
                home_record="1-0",
                road_record="1-0",
                streak="W2",
            ),
            Standing(
                season=2023,
                team_id=lal.id,
                wins=0,
                losses=2,
                win_pct=0.0,
                conference="West",
                conference_rank=1,
                home_record="0-1",
                road_record="0-1",
                streak="L2",
            ),
        ]
    )
    session.add(
        ModelPrediction(
            game_id=game.id,
            model_version="v1",
            predicted_home_win_prob=0.62,
            predicted_home_win=True,
            actual_home_win=True,
            is_correct=True,
            predicted_at=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
            settled_at=None,
        )
    )
    session.add(User(name="test-client", api_key_hash=hash_api_key(API_KEY), is_active=True))
    await session.commit()


@pytest_asyncio.fixture
async def client(tmp_path: pathlib.Path) -> AsyncIterator[httpx.AsyncClient]:
    db_path = tmp_path / "api_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as seed_session:
        await _seed(seed_session)

    from backend.app.api.deps import redis_dep
    from backend.app.db.session import get_session
    from backend.main import app

    fake_redis = FakeAsyncRedis(decode_responses=True)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    async def _override_redis() -> AsyncIterator[FakeAsyncRedis]:
        yield fake_redis

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[redis_dep] = _override_redis

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await fake_redis.aclose()
    await engine.dispose()
