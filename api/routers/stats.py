"""/api/stats — dashboard counters + top domains."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_pool
from ..models import DailyCount, StatsResponse, TopDomain

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def stats(pool=Depends(get_pool)) -> StatsResponse:
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT count(*) FROM blocked_attempts")
        today = await conn.fetchval(
            "SELECT count(*) FROM blocked_attempts "
            "WHERE created_at >= date_trunc('day', now())"
        )
        unique = await conn.fetchval(
            "SELECT count(DISTINCT domain) FROM blocked_attempts"
        )
        top_rows = await conn.fetch(
            """
            SELECT domain, count(*) AS c
            FROM blocked_attempts
            WHERE created_at >= now() - interval '7 days'
            GROUP BY domain
            ORDER BY c DESC
            LIMIT 10
            """
        )
        daily_rows = await conn.fetch(
            """
            SELECT to_char(date_trunc('day', day), 'YYYY-MM-DD') AS day,
                   coalesce(count(b.id), 0) AS c
            FROM generate_series(
                   date_trunc('day', now()) - interval '6 days',
                   date_trunc('day', now()),
                   interval '1 day'
                 ) AS day
            LEFT JOIN blocked_attempts b
                   ON date_trunc('day', b.created_at) = day
            GROUP BY day
            ORDER BY day
            """
        )

    return StatsResponse(
        total_blocked=int(total or 0),
        blocked_today=int(today or 0),
        unique_domains=int(unique or 0),
        top_domains=[TopDomain(domain=r["domain"], count=int(r["c"])) for r in top_rows],
        daily=[DailyCount(day=r["day"], count=int(r["c"])) for r in daily_rows],
    )
