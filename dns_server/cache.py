"""Redis-backed verdict cache + scan queue."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis


VERDICT_SAFE = "safe"
VERDICT_SUSPICIOUS = "suspicious"
VERDICT_SCAM = "scam"
VERDICT_PENDING = "pending"


@dataclass(frozen=True)
class Verdict:
    verdict: str
    risk_score: int = 0
    confidence: int = 0
    reason: str = ""
    source: str = "cache"

    @property
    def is_blocking(self) -> bool:
        return self.verdict in (VERDICT_SCAM, VERDICT_SUSPICIOUS)


class VerdictCache:
    """Thin wrapper over Redis. Keys:

    verdict:<domain>    JSON blob → Verdict
    scamlens:scan_queue list of pending domains
    rl:<domain>         rate-limit marker for scan enqueue
    """

    KEY_PREFIX = "verdict:"
    RATE_LIMIT_PREFIX = "rl:"

    def __init__(self, redis: Redis, queue_key: str):
        self._redis = redis
        self._queue_key = queue_key

    async def get(self, domain: str) -> Optional[Verdict]:
        raw = await self._redis.get(self.KEY_PREFIX + domain)
        if not raw:
            return None
        data = json.loads(raw)
        return Verdict(
            verdict=data["verdict"],
            risk_score=data.get("risk_score", 0),
            confidence=data.get("confidence", 0),
            reason=data.get("reason", ""),
            source=data.get("source", "cache"),
        )

    async def set(self, domain: str, verdict: Verdict, ttl: int) -> None:
        payload = json.dumps({
            "verdict": verdict.verdict,
            "risk_score": verdict.risk_score,
            "confidence": verdict.confidence,
            "reason": verdict.reason,
            "source": verdict.source,
            "ts": int(time.time()),
        })
        await self._redis.set(self.KEY_PREFIX + domain, payload, ex=ttl)

    async def mark_pending(self, domain: str, ttl: int) -> bool:
        """Set pending marker only if no verdict already exists. Returns True
        when we were the one to claim the slot (caller should enqueue scan)."""
        payload = json.dumps({
            "verdict": VERDICT_PENDING,
            "source": "scan_queue",
            "ts": int(time.time()),
        })
        return bool(await self._redis.set(
            self.KEY_PREFIX + domain, payload, ex=ttl, nx=True
        ))

    async def enqueue_scan(self, domain: str) -> None:
        await self._redis.lpush(self._queue_key, domain)

    async def rate_limit_ok(self, domain: str, window: int = 60) -> bool:
        """Prevent flooding the scanner with duplicate enqueues for the same
        domain inside `window` seconds."""
        key = self.RATE_LIMIT_PREFIX + domain
        return bool(await self._redis.set(key, "1", ex=window, nx=True))
