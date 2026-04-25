"""Scanner worker. Pops domains off the Redis queue, runs a pre-filter, then
Playwright + AI. Concurrency bounded by semaphore to cap RAM + API usage.

Pre-filter: RDAP domain age.
    age >= AGE_AUTO_SAFE_DAYS (365) → skip AI, cache 'safe' verdict.
    age unknown or newer            → proceed to fetch + AI as normal.

Skipping AI for aged domains avoids false positives on legit-but-obscure
sites (personal blogs, regional small businesses) and cuts API spend.
"""
from __future__ import annotations

import asyncio

import structlog

from .ai import AIClient, ScanVerdict
from .config import Config
from .fetcher import PageFetcher
from .heuristics import analyze, render_for_prompt, severity_floor
from .rdap import AGE_AUTO_SAFE_DAYS, lookup_age
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
            popped = await self._redis.brpop(self._cfg.scan_queue_key, timeout=5)
            if not popped:
                in_flight = {t for t in in_flight if not t.done()}
                continue
            _, domain = popped
            task = asyncio.create_task(self._run_one(domain))
            in_flight.add(task)
            task.add_done_callback(in_flight.discard)
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)

    def stop(self) -> None:
        self._stop.set()

    async def _run_one(self, domain: str) -> None:
        async with self._sem:
            log.info("scan_start", domain=domain)
            try:
                # Pre-filter: RDAP age.
                age = await lookup_age(domain, self._redis)
                log.info("scan_age", domain=domain, days=age.days)

                if age.known and age.days >= AGE_AUTO_SAFE_DAYS:
                    verdict = ScanVerdict(
                        verdict="safe",
                        risk_score=10,
                        confidence=60,
                        reasons=[f"domain registered {age.days} days ago"],
                        mimics_brand=None,
                        model="rdap-age",
                    )
                    await self._store.save(
                        domain=domain,
                        verdict=verdict,
                        safe_ttl=self._cfg.safe_ttl,
                        scam_ttl=self._cfg.scam_ttl,
                        unknown_ttl=self._cfg.unknown_ttl,
                    )
                    log.info("scan_skip_aged", domain=domain, days=age.days)
                    return

                # Otherwise: full fetch + AI.
                capture = await self._fetcher.fetch(domain)
                if capture is None:
                    await self._store.save_error(
                        domain, "fetch failed", self._cfg.unknown_ttl,
                    )
                    log.info("scan_fetch_failed", domain=domain)
                    return

                heuristics = analyze(capture.html, domain)
                verdict = await self._ai.scan(
                    domain=domain,
                    html=capture.html,
                    screenshot_png=capture.screenshot_png,
                    heuristic_summary=render_for_prompt(heuristics),
                )

                # Post-AI floor — heuristics may force a stricter verdict.
                verdict = _apply_heuristic_floor(verdict, heuristics, domain)

                # If the domain is brand-new AND AI didn't say scam outright,
                # bump suspicion — freshly-registered domains are high-risk
                # per base rates.
                if age.known and age.days is not None and age.days < 14:
                    if verdict.verdict == "safe":
                        verdict = ScanVerdict(
                            verdict="suspicious",
                            risk_score=max(verdict.risk_score, 55),
                            confidence=max(verdict.confidence, 40),
                            reasons=verdict.reasons
                                + [f"domain registered {age.days} days ago"],
                            mimics_brand=verdict.mimics_brand,
                            model=verdict.model,
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
                    age_days=age.days,
                )
            except Exception as exc:
                log.exception("scan_error", domain=domain, error=str(exc))
                await self._store.save_error(
                    domain, f"scan error: {type(exc).__name__}",
                    self._cfg.unknown_ttl,
                )


def _apply_heuristic_floor(
    verdict: ScanVerdict, heuristics, domain: str,
) -> ScanVerdict:
    """If the static scan picked up unmistakable phishing fingerprints,
    promote the verdict to at least the floor severity. AI is the
    flexible signal; heuristics are the safety net."""
    rank = {"safe": 0, "suspicious": 1, "scam": 2}
    floor_verdict, floor_reasons = severity_floor(heuristics, domain)
    if rank[floor_verdict] <= rank[verdict.verdict]:
        return verdict
    extra_score = {"suspicious": 65, "scam": 90}[floor_verdict]
    return ScanVerdict(
        verdict=floor_verdict,
        risk_score=max(verdict.risk_score, extra_score),
        confidence=max(verdict.confidence, 70),
        reasons=verdict.reasons + floor_reasons + ["promoted by static-scan heuristics"],
        mimics_brand=verdict.mimics_brand,
        model=verdict.model,
    )
