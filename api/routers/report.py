"""/api/report — user-submitted scam domain."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..deps import get_pool
from ..models import ReportRequest, ReportResponse
from ..rate_limit import limiter

router = APIRouter()


@router.post("/report", response_model=ReportResponse)
@limiter.limit("10/hour")
async def report(
    request: Request,
    body: ReportRequest,
    pool=Depends(get_pool),
) -> ReportResponse:
    reporter_ip = _client_ip(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_reports (domain, note, reporter_ip, status)
            VALUES ($1, $2, $3::inet, 'pending')
            RETURNING id, domain, status
            """,
            body.domain, body.note, reporter_ip,
        )
    return ReportResponse(**dict(row))


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"
