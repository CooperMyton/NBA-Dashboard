"""Shared fixtures for ETL tests: a fresh migrated SQLite database per test."""

import json
import pathlib
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models import Base

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest_asyncio.fixture
async def session(tmp_path: pathlib.Path) -> AsyncIterator[AsyncSession]:
    db_path = tmp_path / "etl_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as db_session:
        yield db_session
    await engine.dispose()
