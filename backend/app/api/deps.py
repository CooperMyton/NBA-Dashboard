"""Shared FastAPI dependencies: pagination, Redis, and rate limiting."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.errors import rate_limited, unauthorized
from backend.app.core.model import ActiveModel, get_active_model
from backend.app.core.ratelimit import check_rate_limit
from backend.app.core.redis import get_redis
from backend.app.core.security import hash_api_key
from backend.app.db.session import get_session
from backend.app.models.user import User
from backend.app.schemas.envelope import Meta


@dataclass
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


def build_meta(total: int, page: Pagination, count: int) -> Meta:
    return Meta(
        total=total,
        limit=page.limit,
        offset=page.offset,
        has_more=page.offset + count < total,
    )


async def redis_dep() -> AsyncIterator[Redis]:
    redis = get_redis()
    try:
        yield redis
    finally:
        await redis.aclose()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request, redis: Annotated[Redis, Depends(redis_dep)]) -> None:
    settings = get_settings()
    allowed = await check_rate_limit(
        redis, _client_ip(request), limit=settings.api_rate_limit_per_min, window_s=60
    )
    if not allowed:
        raise rate_limited()


PaginationDep = Annotated[Pagination, Depends(pagination)]
RedisDep = Annotated[Redis, Depends(redis_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActiveModelDep = Annotated[ActiveModel, Depends(get_active_model)]


async def require_api_key(
    session: SessionDep, x_api_key: Annotated[str | None, Header()] = None
) -> User:
    if not x_api_key:
        raise unauthorized("Missing X-API-Key header")
    digest = hash_api_key(x_api_key)
    user = (
        await session.execute(
            select(User).where(User.api_key_hash == digest, User.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if user is None:
        raise unauthorized("Invalid API key")
    return user


ApiKeyDep = Annotated[User, Depends(require_api_key)]
