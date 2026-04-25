"""ScamLens API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncpg
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

import asyncio

from .config import Config
from .events import EventBus, run_subscriber
from .push import PushSender
from .rate_limit import limiter
from .routers import (
    admin, auth, blocked, check, deep, events, geo, me, push, report, setup, stats,
)


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.from_env()
    _setup_logging(cfg.log_level)
    log = structlog.get_logger()
    log.info("api_boot", domain=cfg.domain)

    app.state.cfg = cfg
    app.state.pg_pool = await asyncpg.create_pool(
        cfg.database_url, min_size=1, max_size=10, command_timeout=10,
    )
    app.state.redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    app.state.push = PushSender(
        cfg.vapid_public_key, cfg.vapid_private_key, cfg.vapid_contact,
    )
    app.state.event_bus = EventBus()

    # Background: listen to Redis pubsub for block events, fan out push + SSE.
    subscriber_task = asyncio.create_task(
        run_subscriber(
            app.state.redis, app.state.pg_pool,
            app.state.push, app.state.event_bus,
        )
    )

    yield

    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    await app.state.pg_pool.close()
    await app.state.redis.aclose()


_boot_cfg = Config.from_env()

app = FastAPI(title="ScamLens API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_boot_cfg.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(stats.router, prefix="/api")
app.include_router(blocked.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(check.router, prefix="/api")
app.include_router(setup.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(geo.router, prefix="/api")
app.include_router(deep.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(push.router, prefix="/api")
app.include_router(events.router, prefix="/api")
