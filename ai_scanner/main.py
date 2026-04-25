"""ScamLens AI scanner entrypoint."""
from __future__ import annotations

import asyncio
import logging
import signal

import asyncpg
import structlog
from redis.asyncio import Redis

from .ai import build_client
from .config import Config
from .fetcher import PageFetcher
from .store import VerdictStore
from .worker import Worker


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )


async def run() -> None:
    cfg = Config.from_env()
    _setup_logging(cfg.log_level)
    log = structlog.get_logger()
    active_model = {
        "anthropic": cfg.anthropic_model,
        "gemini": cfg.gemini_model,
        "qwen": cfg.qwen_model,
    }.get(cfg.ai_provider, "?")
    log.info("scanner_boot", provider=cfg.ai_provider, model=active_model)

    redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    pg_pool = await asyncpg.create_pool(
        cfg.database_url, min_size=1, max_size=4, command_timeout=10,
    )
    ai = build_client(cfg.ai_provider, cfg)
    store = VerdictStore(redis, pg_pool)
    fetcher = PageFetcher(cfg.scan_timeout, cfg.max_html_chars, cfg.screenshot_max_bytes)
    await fetcher.start()
    worker = Worker(cfg, redis, fetcher, ai, store)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: (worker.stop(), stop.set()))

    runner = asyncio.create_task(worker.run())
    await stop.wait()
    log.info("scanner_shutting_down")
    await runner

    await fetcher.close()
    await pg_pool.close()
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
