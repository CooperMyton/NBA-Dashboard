"""Liveness (`/health`) and readiness (`/ready`) probes.

``/health`` confirms the process responds (no dependency checks — for liveness).
``/ready`` checks DB and Redis connectivity and returns 503 if either is down, so an
orchestrator takes the instance out of rotation without killing it.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.api.deps import RedisDep, SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, dict[str, str]]:
    return {"data": {"status": "ok"}}


@router.get("/ready")
async def ready(session: SessionDep, redis: RedisDep) -> JSONResponse:
    checks = {"database": False, "redis": False}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001 - report as not-ready, don't crash the probe
        pass

    try:
        await redis.ping()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass

    ready_ok = all(checks.values())
    body = {"data": {"status": "ready" if ready_ok else "not_ready", "checks": checks}}
    return JSONResponse(status_code=200 if ready_ok else 503, content=body)
