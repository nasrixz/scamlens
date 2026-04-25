"""/api/geo/{ip} — proxy to ipwho.is with Redis cache.

Why proxy instead of letting the browser hit ipwho.is directly?
  * Cache once on the server, reuse for every viewer.
  * Survives provider outages and rate-limit changes.
  * Lets us swap the upstream provider later without updating clients.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_redis

router = APIRouter()

CACHE_PREFIX = "geo:"
CACHE_TTL = 30 * 24 * 3600   # 30 days
UPSTREAM = "https://ipwho.is/"
TIMEOUT = 5.0

IP_RE = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[0-9a-fA-F:]+)$"
)


@router.get("/geo/{ip}")
async def geo(ip: str, redis=Depends(get_redis)) -> dict[str, Any]:
    if not IP_RE.match(ip):
        raise HTTPException(400, "invalid ip")

    cached = await redis.get(CACHE_PREFIX + ip)
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            resp = await c.get(UPSTREAM + ip)
        data = resp.json()
    except Exception as exc:
        raise HTTPException(502, f"geo lookup failed: {exc}")

    if not data.get("success", True):
        # ipwho.is returns success=false for unroutable / private IPs
        slim = {"ip": ip, "success": False, "message": data.get("message")}
        await redis.set(CACHE_PREFIX + ip, json.dumps(slim), ex=3600)
        return slim

    slim = {
        "ip": data.get("ip"),
        "success": True,
        "type": data.get("type"),
        "country": data.get("country"),
        "country_code": data.get("country_code"),
        "region": data.get("region"),
        "city": data.get("city"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "flag_emoji": (data.get("flag") or {}).get("emoji"),
        "timezone": (data.get("timezone") or {}).get("id"),
        "connection": {
            "asn": (data.get("connection") or {}).get("asn"),
            "org": (data.get("connection") or {}).get("org"),
            "isp": (data.get("connection") or {}).get("isp"),
            "domain": (data.get("connection") or {}).get("domain"),
        },
    }
    await redis.set(CACHE_PREFIX + ip, json.dumps(slim), ex=CACHE_TTL)
    return slim
