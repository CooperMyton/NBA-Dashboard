"""FastAPI application entrypoint.

Routes stay thin (validation + service call + response). App wiring lives here; business
logic lives in ``backend/app/services``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.errors import register_exception_handlers
from backend.app.core.logging import configure_logging, get_logger
from backend.app.core.model import active_model

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    try:
        active_model.load()
    except Exception as exc:  # noqa: BLE001 - a missing/broken model must not block startup
        get_logger("api").warning("model.load_failed", error=str(exc))
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="NBA Analytics Platform",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
