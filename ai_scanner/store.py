"""Verdict persistence — Redis cache + Postgres domain_verdicts row."""
from __future__ import annotations

import json
import time
from typing import Optional

import asyncpg
import structlog
from redis.asyncio import Redis

from .ai import ScanVerdict

log = structlog.get_logger()

VERDICT_CACHE_PREFIX = "verdict:"


class VerdictStore:
    def __init__(self, redis: Redis, pg_pool: asyncpg.Pool):
        self._redis = redis
        self._pool = pg_pool

    async def save(
        self,
        domain: str,
        verdict: ScanVerdict,
        safe_ttl: int,
        scam_ttl: int,
        unknown_ttl: int,
    ) -> None:
        ttl = _pick_ttl(verdict.verdict, safe_ttl, scam_ttl, unknown_ttl)
        payload = json.dumps({
            "verdict": verdict.verdict,
            "risk_score": verdict.risk_score,
            "confidence": verdict.confidence,
            "reason": verdict.primary_reason,
            "mimics_brand": verdict.mimics_brand,
            "source": "ai",
            "model": verdict.model,
            "ts": int(time.time()),
        })
        await self._redis.set(VERDICT_CACHE_PREFIX + domain, payload, ex=ttl)

        try:
            await self._pool.execute(
                """
                INSERT INTO domain_verdicts
                  (domain, verdict, risk_score, confidence, reasons,
                   mimics_brand, source, updated_at)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, 'ai', now())
                ON CONFLICT (domain) DO UPDATE SET
                  verdict      = EXCLUDED.verdict,
                  risk_score   = EXCLUDED.risk_score,
                  confidence   = EXCLUDED.confidence,
                  reasons      = EXCLUDED.reasons,
                  mimics_brand = EXCLUDED.mimics_brand,
                  source       = 'ai',
                  updated_at   = now()
                """,
                domain,
                verdict.verdict,
                verdict.risk_score,
                verdict.confidence,
                json.dumps(verdict.reasons),
                verdict.mimics_brand,
            )
        except Exception as exc:
            log.warning("verdict_pg_write_failed", domain=domain, error=str(exc))

    async def save_error(self, domain: str, reason: str, unknown_ttl: int) -> None:
        """Cache a short-lived 'could not verify' marker so we don't retry
        the same broken domain in a tight loop."""
        payload = json.dumps({
            "verdict": "suspicious",
            "risk_score": 30,
            "confidence": 5,
            "reason": reason,
            "source": "scan_error",
            "ts": int(time.time()),
        })
        await self._redis.set(
            VERDICT_CACHE_PREFIX + domain, payload, ex=unknown_ttl,
        )


def _pick_ttl(v: str, safe: int, scam: int, unknown: int) -> int:
    if v == "safe":
        return safe
    if v == "scam":
        return scam
    return unknown  # suspicious
