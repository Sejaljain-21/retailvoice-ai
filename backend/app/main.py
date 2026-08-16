"""FastAPI application factory and entrypoint."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_database
from app.ws.voice_ws import router as voice_ws_router

configure_logging()
log = get_logger(__name__)

DESCRIPTION = """
**RetailVoice AI** - an AI customer-support and voice agent for e-commerce and retail.

* `POST /api/v1/chat/message` - text conversation with the agent
* `POST /api/v1/voice/turn` - one complete voice turn (audio in, audio out)
* `WS  /ws/voice` - streaming voice session
* `GET /api/v1/analytics/dashboard` - containment, CSAT, intents, tool usage

The agent is grounded: order, stock and policy claims all come from tool calls
against the live database and the retrieval index, never from model memory.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting %s v%s (%s)", settings.APP_NAME, __version__, settings.APP_ENV)
    await init_database(seed=settings.SEED_ON_STARTUP)
    log.info("API docs: http://localhost:8000/docs")
    yield
    log.info("Shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description=DESCRIPTION,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time-Ms"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("Request failed: %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "internal_error",
                                   "message": "An unexpected error occurred."}},
            )
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.1f}"
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(voice_ws_router)

    @app.get("/", tags=["system"])
    async def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": __version__,
            "docs": "/docs",
            "api": settings.API_V1_PREFIX,
            "voice_websocket": "/ws/voice",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.APP_ENV == "development",
    )
