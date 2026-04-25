"""/api/check/{domain} — on-demand lookup. Returns cached verdict or enqueues
a scan and reports 'pending'. Dashboard polls until verdict lands."""
from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import get_cfg, get_pool, get_redis
from ..models import CheckResponse
from ..rate_limit import limiter

router = APIRouter()

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


@router.get("/check/{domain}", response_model=CheckResponse)
@limiter.limit("30/hour")
async def check(
    request: Request,
    domain: str,
    cfg=Depends(get_cfg),
    pool=Depends(get_pool),
    redis=Depends(get_redis),
) -> CheckResponse:
    normalized = domain.strip().lower().rstrip(".")
    if not DOMAIN_RE.match(normalized):
        raise HTTPException(status_code=400, detail="invalid domain")

    # 0. Blocklist beats everything else, even a stale 'safe' AI verdict.
    bl = await _blocklist_match(pool, normalized)
    if bl:
        resolved_ip = await _latest_resolved_ip(pool, normalized)
        return CheckResponse(
            domain=normalized,
            verdict="scam",
            risk_score=100,
            confidence=100,
            reason=f"on blocklist ({bl})",
            mimics_brand=None,
            resolved_ip=resolved_ip,
            source="blocklist",
            cached=False,
        )

    # 1. Redis cache (freshest — scanner writes here)
    raw = await redis.get(f"verdict:{normalized}")
    if raw:
        data = json.loads(raw)
        resolved_ip = await _latest_resolved_ip(pool, normalized)
        return CheckResponse(
            domain=normalized,
            verdict=data.get("verdict", "unknown"),
            risk_score=data.get("risk_score"),
            confidence=data.get("confidence"),
            reason=data.get("reason"),
            mimics_brand=data.get("mimics_brand"),
            resolved_ip=resolved_ip,
            source=data.get("source", "cache"),
            cached=True,
        )

    # 2. Postgres fallback (older verdict AI may have expired in Redis)
    row = await _pg_verdict(pool, normalized)
    if row:
        resolved_ip = await _latest_resolved_ip(pool, normalized)
        return CheckResponse(
            domain=normalized,
            verdict=row["verdict"],
            risk_score=row["risk_score"],
            confidence=row["confidence"],
            reason=_first_reason(row["reasons"]),
            mimics_brand=row["mimics_brand"],
            resolved_ip=resolved_ip,
            source=row["source"],
            cached=False,
        )

    # 3. Trigger scan + return pending so caller can poll
    await redis.lpush(cfg.scan_queue_key, normalized)
    return CheckResponse(
        domain=normalized, verdict="pending", source="scan_enqueued", cached=False,
    )


async def _pg_verdict(pool, domain: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT verdict, risk_score, confidence, reasons, mimics_brand, source
            FROM domain_verdicts WHERE domain = $1
            """,
            domain,
        )


async def _blocklist_match(pool, domain: str) -> Optional[str]:
    """Walk parent chain against blocklist_seed + confirmed user reports.
    Returns the matched category/source or None."""
    parts = domain.split(".")
    candidates = [".".join(parts[i:]) for i in range(len(parts) - 1)]
    if not candidates:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT category FROM blocklist_seed WHERE domain = ANY($1::text[])
            ORDER BY length(domain) DESC LIMIT 1
            """,
            candidates,
        )
    return row["category"] if row else None


async def _latest_resolved_ip(pool, domain: str) -> Optional[str]:
    """Return the resolved_ip from the latest blocked_attempts row.
    `host()` strips the /32 (or /128) suffix Postgres adds for INET."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT host(resolved_ip) FROM blocked_attempts
            WHERE domain = $1 AND resolved_ip IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            domain,
        )


def _first_reason(reasons_json) -> Optional[str]:
    if not reasons_json:
        return None
    try:
        reasons = reasons_json if isinstance(reasons_json, list) else json.loads(reasons_json)
        return reasons[0] if reasons else None
    except Exception:
        return None
