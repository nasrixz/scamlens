"""ScamLens DNS server entrypoint.

Starts three listeners (UDP/TCP on :53, DoH on :8053) backed by a single
Resolver instance with Redis cache + Postgres logging + upstream forwarder.
"""
from __future__ import annotations

import asyncio
import logging
import signal

import structlog
from redis.asyncio import Redis

from .cache import VerdictCache
from .config import Config
from .db import Database
from .resolver import Resolver
from .servers import start_doh, start_tcp, start_udp
from .upstream import UpstreamResolver


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


async def _refresh_blocklist_loop(db: Database, blocklist: set[str], interval: int = 300):
    log = structlog.get_logger()
    while True:
        try:
            rows = await db.load_blocklist()
            blocklist.clear()
            blocklist.update(rows)
            log.info("blocklist_refreshed", count=len(blocklist))
        except Exception as exc:
            log.warning("blocklist_refresh_failed", error=str(exc))
        await asyncio.sleep(interval)


async def run() -> None:
    cfg = Config.from_env()
    _setup_logging(cfg.log_level)
    log = structlog.get_logger()
    log.info("boot", dns_port=cfg.dns_port, doh_port=cfg.doh_port, upstream=cfg.upstream_dns)

    # Deps
    redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    db = Database(cfg.database_url)
    await db.connect()
    cache = VerdictCache(redis, cfg.scan_queue_key)
    upstream = UpstreamResolver(cfg.upstream_dns, cfg.upstream_dns_fallback)
    blocklist: set[str] = set(await db.load_blocklist())
    log.info("blocklist_loaded", count=len(blocklist))
    resolver = Resolver(cfg, cache, db, upstream, blocklist)

    # Listeners
    udp = await start_udp(resolver, cfg.bind_host, cfg.dns_port)
    tcp = await start_tcp(resolver, cfg.bind_host, cfg.dns_port)
    doh = await start_doh(resolver, cfg.bind_host, cfg.doh_port)

    # Background blocklist refresh so reports/AI verdicts in Postgres
    # get promoted to the in-memory set without a restart.
    refresh_task = asyncio.create_task(
        _refresh_blocklist_loop(db, blocklist, interval=300)
    )

    # Graceful shutdown
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    log.info("shutting_down")
    refresh_task.cancel()
    udp.close()
    tcp.close()
    await tcp.wait_closed()
    await doh.cleanup()
    await db.close()
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
