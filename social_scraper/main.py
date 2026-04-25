"""ScamLens social scraper entrypoint.

Internal scheduler: every `interval_hours` (default 24h) it runs a window
of `duration_minutes` (default 60m) collecting posts from Threads keyword
search and promoting confidently-scammy URLs into the blocklist.

Single source of timing — no external cron needed. Restarting the
container resets the timer; first window runs immediately after boot.
"""
from __future__ import annotations

import asyncio
import logging
import signal

import asyncpg
import structlog
from redis.asyncio import Redis

from .config import Config
from .threads_client import ThreadsClient
from .worker import ScrapeWorker


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

    if not cfg.threads_token:
        log.warning("scraper_disabled", reason="THREADS_ACCESS_TOKEN not set")
        # Sleep forever; orchestrator restart will pick up token.
        while True:
            await asyncio.sleep(3600)

    log.info(
        "scraper_boot",
        keywords=len(cfg.keywords),
        duration_min=cfg.duration_minutes,
        interval_hr=cfg.interval_hours,
    )

    pool = await asyncpg.create_pool(
        cfg.database_url, min_size=1, max_size=4, command_timeout=10,
    )
    redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    client = ThreadsClient(cfg.threads_token, search_type=cfg.threads_search_type)
    worker = ScrapeWorker(cfg, pool, redis, client)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        while not stop.is_set():
            try:
                await worker.run_window()
            except Exception as exc:
                log.exception("scrape_window_failed", error=str(exc))
            # Sleep until next window.
            sleep_for = max(60, cfg.interval_hours * 3600 - cfg.duration_minutes * 60)
            log.info("scraper_idle", sleep_seconds=sleep_for)
            try:
                await asyncio.wait_for(stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass
    finally:
        await pool.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
