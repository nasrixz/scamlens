"""Scanner worker. Pops domains off the Redis queue, runs Playwright fetch +
AI, writes verdict. Concurrency bounded by semaphore to cap RAM + API usage."""
from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from .ai import AIClient
from .config import Config
from .fetcher import PageFetcher
from .store import VerdictStore

log = structlog.get_logger()


class Worker:
    def __init__(
        self,
        cfg: Config,
        redis,
        fetcher: PageFetcher,
        ai: AIClient,
        store: VerdictStore,
    ):
        self._cfg = cfg
        self._redis = redis
        self._fetcher = fetcher
        self._ai = ai
        self._store = store
        self._sem = asyncio.Semaphore(cfg.concurrency)
        self._stop = asyncio.Event()

    async def run(self) -> None:
        log.info("worker_started", concurrency=self._cfg.concurrency)
        in_flight: set[asyncio.Task] = set()
        while not self._stop.is_set():
            # BRPOP blocks up to 5s so we can notice shutdown promptly.
            popped = await self._redis.brpop(self._cfg.scan_queue_key, timeout=5)
            if not popped:
                # Harvest any finished tasks so the set doesn't grow forever.
                in_flight = {t for t in in_flight if not t.done()}
                continue
            _, domain = popped
            task = asyncio.create_task(self._run_one(domain))
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)
        # Drain in-flight work on shutdown.
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)

    def stop(self) -> None:
        self._stop.set()

    async def _run_one(self, domain: str) -> None:
        async with self._sem:
            log.info("scan_start", domain=domain)
            try:
                capture = await self._fetcher.fetch(domain)
                if capture is None:
                    await self._store.save_error(
                        domain, "fetch failed", self._cfg.unknown_ttl,
                    )
                    log.info("scan_fetch_failed", domain=domain)
                    return

                verdict = await self._ai.scan(
                    domain=domain,
                    html=capture.html,
                    screenshot_png=capture.screenshot_png,
                )
                await self._store.save(
                    domain=domain,
                    verdict=verdict,
                    safe_ttl=self._cfg.safe_ttl,
                    scam_ttl=self._cfg.scam_ttl,
                    unknown_ttl=self._cfg.unknown_ttl,
                )
                log.info(
                    "scan_done",
                    domain=domain,
                    verdict=verdict.verdict,
                    risk=verdict.risk_score,
                    conf=verdict.confidence,
                    mimics=verdict.mimics_brand,
                )
            except Exception as exc:
                log.exception("scan_error", domain=domain, error=str(exc))
                await self._store.save_error(
                    domain, f"scan error: {type(exc).__name__}",
                    self._cfg.unknown_ttl,
                )
