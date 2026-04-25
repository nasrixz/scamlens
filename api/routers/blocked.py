"""/api/blocked — paginated + filterable list of block events."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..deps import get_pool
from ..models import BlockedPage, BlockedRow

router = APIRouter()


@router.get("/blocked", response_model=BlockedPage)
async def blocked(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None, description="substring match on domain"),
    pool=Depends(get_pool),
) -> BlockedPage:
    offset = (page - 1) * page_size

    where = ""
    args: list = []
    if q:
        where = "WHERE domain ILIKE $1"
        args.append(f"%{q}%")

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM blocked_attempts {where}", *args
        )
        list_args = args + [page_size, offset]
        rows = await conn.fetch(
            f"""
            SELECT id, domain, reason, verdict, ai_confidence, risk_score,
                   mimics_brand, country, resolved_ip::text AS resolved_ip,
                   created_at
            FROM blocked_attempts
            {where}
            ORDER BY created_at DESC
            LIMIT ${len(list_args) - 1} OFFSET ${len(list_args)}
            """,
            *list_args,
        )

    items = [BlockedRow(**dict(r)) for r in rows]
    return BlockedPage(
        items=items, total=int(total or 0), page=page, page_size=page_size,
    )
