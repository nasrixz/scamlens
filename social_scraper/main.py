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
from aiohttp import web
from redis.asyncio import Redis

from .config import Config
from .control import LOCK_KEY, LOCK_TTL, build_app as build_control_app
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
        log.warning(
            "threads_token_missing",
            note="Threads source disabled. URLhaus + Reddit still work.",
        )

    log.info(
        "scraper_boot",
        keywords=len(cfg.keywords),
        duration_min=cfg.duration_minutes,
        interval_hr=cfg.interval_hours,
        threads=bool(cfg.threads_token),
    )

    pool = await asyncpg.create_pool(
        cfg.database_url, min_size=1, max_size=4, command_timeout=10,
    )
    redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    client = ThreadsClient(cfg.threads_token, search_type=cfg.threads_search_type)
    worker = ScrapeWorker(cfg, pool, redis, client)

    # Internal HTTP control endpoint for manual triggers.
    control_app = build_control_app(cfg, worker, redis)
    control_runner = web.AppRunner(control_app, access_log=None)
    await control_runner.setup()
    control_site = web.TCPSite(control_runner, host="0.0.0.0", port=8091)
    await control_site.start()
    log.info("scraper_control_listening", port=8091)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        # Cron-driven sources. URLhaus is always-on (free, classified).
        # Threads only runs if a token is set; Reddit always runs.
        cron_sources = ["urlhaus", "reddit"]
        if cfg.threads_token:
            cron_sources.append("threads")

        while not stop.is_set():
            for source in cron_sources:
                if stop.is_set():
                    break
                # Acquire lock so a manual run can't collide.
                claimed = await redis.set(LOCK_KEY, f"cron:{source}", ex=LOCK_TTL, nx=True)
                if claimed:
                    try:
                        log.info("cron_source_start", source=source)
                        await worker.run_window(source=source)
                    except Exception as exc:
                        log.exception("scrape_window_failed", source=source, error=str(exc))
                    finally:
                        await redis.delete(LOCK_KEY)
                else:
                    log.info("scrape_skipped", source=source, reason="manual run in progress")

            sleep_for = max(60, cfg.interval_hours * 3600 - cfg.duration_minutes * 60)
            log.info("scraper_idle", sleep_seconds=sleep_for)
            try:
                await asyncio.wait_for(stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass
    finally:
        await control_runner.cleanup()
        await pool.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
