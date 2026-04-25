"""/api/deep/{domain} — kick off / fetch a 'deep' scan.

Fast lane (already on the block page server-render): blocklist + typosquat
+ RDAP age + geo + cached AI verdict. Synchronous, sub-second.

Deep lane (this module): a fresh full Playwright fetch + AI verdict +
outbound-link triage. Blocking call to the scanner takes 10-60s, so we
expose two endpoints:

  POST /api/deep/{domain}  — start (non-blocking returning quickly with
                             pending=true, or done=true if cache fresh).
  GET  /api/deep/{domain}  — read current state. Block page polls.

Result shape mirrors what the admin /scan endpoint already returns.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import get_redis
from ..rate_limit import limiter

router = APIRouter()

DEEP_KEY_PREFIX = "deep:"
DEEP_LOCK_PREFIX = "deep_lock:"
DEEP_TTL_SECONDS = 6 * 3600          # 6h cache for completed deep results
DEEP_LOCK_TTL = 90                   # max scan duration we wait for
SCANNER_URL = os.getenv("SCANNER_URL", "http://ai_scanner:8090")

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


@router.get("/deep/{domain}")
async def deep_get(domain: str, redis=Depends(get_redis)):
    d = _norm(domain)
    raw = await redis.get(DEEP_KEY_PREFIX + d)
    if raw:
        return {"status": "done", "domain": d, "report": json.loads(raw)}

    # Anything in flight? Show pending.
    if await redis.get(DEEP_LOCK_PREFIX + d):
        return {"status": "pending", "domain": d}

    return {"status": "idle", "domain": d}


@router.post("/deep/{domain}")
@limiter.limit("20/hour")
async def deep_post(request: Request, domain: str, redis=Depends(get_redis)):
    """Trigger a deep scan if not already running. Public endpoint, rate-
    limited per IP. Block page calls it when first rendering."""
    d = _norm(domain)

    cached = await redis.get(DEEP_KEY_PREFIX + d)
    if cached:
        return {"status": "done", "domain": d, "report": json.loads(cached)}

    claimed = await redis.set(
        DEEP_LOCK_PREFIX + d, "1", ex=DEEP_LOCK_TTL, nx=True,
    )
    if not claimed:
        return {"status": "pending", "domain": d}

    # Fire-and-forget the scan. Result written under deep:<domain>.
    asyncio.create_task(_run_deep_scan(d, redis))
    return {"status": "pending", "domain": d}


async def _run_deep_scan(domain: str, redis) -> None:
    try:
        async with httpx.AsyncClient(timeout=DEEP_LOCK_TTL) as c:
            resp = await c.post(
                f"{SCANNER_URL}/scan",
                json={"url": f"http://{domain}"},
            )
        if resp.status_code != 200:
            error_payload = {
                "fetched": False,
                "domain": domain,
                "error": f"scanner returned {resp.status_code}",
            }
            await redis.set(
                DEEP_KEY_PREFIX + domain,
                json.dumps(error_payload),
                ex=300,  # short TTL on error so we retry sooner
            )
            return

        report = resp.json()
        await redis.set(
            DEEP_KEY_PREFIX + domain,
            json.dumps(report),
            ex=DEEP_TTL_SECONDS,
        )
    except Exception as exc:
        await redis.set(
            DEEP_KEY_PREFIX + domain,
            json.dumps({"fetched": False, "domain": domain, "error": str(exc)[:300]}),
            ex=300,
        )
    finally:
        await redis.delete(DEEP_LOCK_PREFIX + domain)


def _norm(domain: str) -> str:
    n = domain.strip().lower().rstrip(".")
    if not DOMAIN_RE.match(n):
        raise HTTPException(400, "invalid domain")
    return n
