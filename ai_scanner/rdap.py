"""RDAP-based domain age lookup.

Used as a pre-filter before the expensive Playwright + AI scan. Cheap
(~50-200ms HTTP call) and domain age is a strong signal:

  age > 1 year  → almost certainly not a freshly-registered scam domain
  age < 14 days → definitely worth scanning

Public RDAP aggregator at https://rdap.org follows the IANA bootstrap
referral automatically, so one URL handles every TLD.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from redis.asyncio import Redis

log = structlog.get_logger()


RDAP_CACHE_PREFIX = "rdap:"
RDAP_CACHE_TTL = 90 * 24 * 3600  # 90 days — age doesn't change fast
RDAP_TIMEOUT = 5.0
RDAP_BASE = "https://rdap.org/domain/"


@dataclass
class DomainAge:
    days: Optional[int]          # None when we couldn't determine
    registered_at: Optional[str] # ISO timestamp or None

    @property
    def known(self) -> bool:
        return self.days is not None


async def lookup_age(domain: str, redis: Redis) -> DomainAge:
    key = RDAP_CACHE_PREFIX + _registered_label(domain)
    cached = await redis.get(key)
    if cached:
        data = json.loads(cached)
        return DomainAge(days=data.get("days"), registered_at=data.get("registered_at"))

    registered_at = await _fetch_rdap_registration(domain)
    days = _days_since(registered_at) if registered_at else None
    await redis.set(
        key,
        json.dumps({"days": days, "registered_at": registered_at}),
        ex=RDAP_CACHE_TTL,
    )
    return DomainAge(days=days, registered_at=registered_at)


async def _fetch_rdap_registration(domain: str) -> Optional[str]:
    """Query rdap.org and return the 'registration' eventDate, or None if
    the TLD is unsupported / query fails."""
    target = _registered_label(domain)
    url = RDAP_BASE + target
    try:
        async with httpx.AsyncClient(timeout=RDAP_TIMEOUT, follow_redirects=True) as c:
            resp = await c.get(url)
        if resp.status_code != 200:
            log.info("rdap_miss", domain=target, status=resp.status_code)
            return None
        data = resp.json()
    except Exception as exc:
        log.info("rdap_error", domain=target, error=str(exc)[:120])
        return None

    events = data.get("events") or []
    for e in events:
        if e.get("eventAction") == "registration":
            return e.get("eventDate")
    return None


def _registered_label(domain: str) -> str:
    """Return the registrable domain (eTLD+1). Simple heuristic that handles
    common compound TLDs. Good enough for RDAP lookup."""
    parts = domain.lower().strip(".").split(".")
    if len(parts) < 2:
        return domain
    compound = {"co.uk", "com.my", "com.au", "com.sg", "com.br", "co.jp", "co.kr", "com.cn"}
    tail = ".".join(parts[-2:])
    if tail in compound and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _days_since(iso_ts: str) -> Optional[int]:
    try:
        # RDAP timestamps are RFC 3339 / ISO 8601 with 'Z' or offset.
        ts = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, delta.days)
    except Exception:
        return None


# ----- decision helpers used by the worker ---------------------------------

# Tunable thresholds.
AGE_AUTO_SAFE_DAYS = 365      # >= this → skip AI, write safe verdict
AGE_SUSPICIOUS_DAYS = 7       # strict lower bound that raises risk
