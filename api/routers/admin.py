"""/api/admin/* — auth + report moderation + blocklist/whitelist CRUD.

All routes except /login require a valid admin session (cookie or Bearer).
"""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from ..auth import (
    AdminPrincipal,
    COOKIE_NAME,
    current_admin,
    fetch_admin_by_email,
    issue_token,
    touch_last_login,
    verify_password,
)
from ..deps import get_cfg, get_pool
from ..rate_limit import limiter

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------- models --------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class DomainEntry(BaseModel):
    domain: str = Field(..., min_length=3, max_length=253)
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("domain")
    @classmethod
    def _norm(cls, v: str) -> str:
        v = v.strip().lower().rstrip(".")
        for p in ("https://", "http://"):
            if v.startswith(p):
                v = v[len(p):]
        v = v.split("/")[0].split("?")[0]
        if "." not in v or " " in v:
            raise ValueError("invalid domain")
        return v


class BrandEntry(BaseModel):
    domain: str
    brand: str
    category: Optional[str] = None

    @field_validator("domain")
    @classmethod
    def _norm(cls, v: str) -> str:
        return v.strip().lower().rstrip(".")


class ReportRow(BaseModel):
    id: int
    domain: str
    note: Optional[str]
    status: str
    reporter_ip: Optional[str]
    created_at: str


class CountsResponse(BaseModel):
    pending_reports: int
    blocklist: int
    whitelist: int
    brands: int


# ------------------------------- auth ----------------------------------------

@router.post("/login")
@limiter.limit("20/hour")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest = Body(...),
    cfg=Depends(get_cfg),
    pool=Depends(get_pool),
):
    admin = await fetch_admin_by_email(pool, body.email)
    if not admin or not verify_password(body.password, admin["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token = issue_token(cfg, admin["id"], admin["email"], admin["role"])
    await touch_last_login(pool, admin["id"])
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=cfg.jwt_ttl_hours * 3600,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"email": admin["email"], "role": admin["role"]}


@router.post("/logout")
async def logout(response: Response, _=Depends(current_admin)):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(who: AdminPrincipal = Depends(current_admin)):
    return {"id": who.id, "email": who.email, "role": who.role}


# ------------------------------- dashboard -----------------------------------

@router.get("/counts", response_model=CountsResponse)
async def counts(
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        pending = await conn.fetchval(
            "SELECT count(*) FROM user_reports WHERE status='pending'"
        )
        bl = await conn.fetchval("SELECT count(*) FROM blocklist_seed")
        wl = await conn.fetchval("SELECT count(*) FROM whitelist")
        br = await conn.fetchval("SELECT count(*) FROM brand_domains")
    return CountsResponse(
        pending_reports=int(pending or 0),
        blocklist=int(bl or 0),
        whitelist=int(wl or 0),
        brands=int(br or 0),
    )


# ------------------------------- reports -------------------------------------

@router.get("/reports")
async def list_reports(
    status_filter: str = "pending",
    limit: int = 100,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    if status_filter not in ("pending", "confirmed", "rejected", "all"):
        raise HTTPException(400, "bad status filter")
    async with pool.acquire() as conn:
        if status_filter == "all":
            rows = await conn.fetch(
                """
                SELECT id, domain, note, status, reporter_ip::text AS reporter_ip,
                       to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') AS created_at
                FROM user_reports ORDER BY created_at DESC LIMIT $1
                """,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, domain, note, status, reporter_ip::text AS reporter_ip,
                       to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') AS created_at
                FROM user_reports WHERE status=$1
                ORDER BY created_at DESC LIMIT $2
                """,
                status_filter, limit,
            )
    return {"items": [dict(r) for r in rows]}


@router.post("/reports/{report_id}/confirm")
async def confirm_report(
    report_id: int,
    who: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "UPDATE user_reports SET status='confirmed' WHERE id=$1 RETURNING domain",
                report_id,
            )
            if not row:
                raise HTTPException(404, "report not found")
            await conn.execute(
                """
                INSERT INTO blocklist_seed (domain, category)
                VALUES ($1, 'user-report')
                ON CONFLICT (domain) DO NOTHING
                """,
                row["domain"],
            )
    return {"id": report_id, "domain": row["domain"], "status": "confirmed", "by": who.email}


@router.post("/reports/{report_id}/reject")
async def reject_report(
    report_id: int,
    who: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE user_reports SET status='rejected' WHERE id=$1 RETURNING domain",
            report_id,
        )
        if not row:
            raise HTTPException(404, "report not found")
    return {"id": report_id, "status": "rejected", "by": who.email}


# ------------------------------- blocklist -----------------------------------

@router.get("/blocklist")
async def list_blocklist(
    limit: int = 500,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    """Returns blocklist_seed rows. Auto-populated by:
      - manual seed (category = scam-* / typosquat-* / test)
      - typosquat detector hits (category = typosquat-<brand>)
      - confirmed user reports (category = user-report)
      - AI scanner with high confidence (category = ai-confirmed)
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT domain, category, source_post, source_platform, added_at "
            "FROM blocklist_seed ORDER BY added_at DESC LIMIT $1",
            limit,
        )
    return {"items": [dict(r) for r in rows]}


@router.post("/blocklist")
async def add_blocklist(
    body: DomainEntry,
    who: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO blocklist_seed (domain, category) VALUES ($1, $2)
            ON CONFLICT (domain) DO NOTHING
            """,
            body.domain, body.reason or "manual",
        )
        # Remove from whitelist if present (admin is explicit: block wins)
        await conn.execute("DELETE FROM whitelist WHERE domain=$1", body.domain)
    return {"domain": body.domain, "added_by": who.email}


@router.delete("/blocklist/{domain}")
async def remove_blocklist(
    domain: str,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    domain = domain.strip().lower().rstrip(".")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM blocklist_seed WHERE domain=$1", domain)
    return {"removed": domain}


# ------------------------------- whitelist -----------------------------------

@router.get("/whitelist")
async def list_whitelist(
    limit: int = 500,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT domain, reason, added_by, added_at FROM whitelist ORDER BY added_at DESC LIMIT $1",
            limit,
        )
    return {"items": [dict(r) for r in rows]}


@router.post("/whitelist")
async def add_whitelist(
    body: DomainEntry,
    who: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO whitelist (domain, reason, added_by) VALUES ($1, $2, $3)
            ON CONFLICT (domain) DO UPDATE SET reason=EXCLUDED.reason, added_by=EXCLUDED.added_by
            """,
            body.domain, body.reason, who.email,
        )
        await conn.execute("DELETE FROM blocklist_seed WHERE domain=$1", body.domain)
    return {"domain": body.domain, "added_by": who.email}


@router.delete("/whitelist/{domain}")
async def remove_whitelist(
    domain: str,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    domain = domain.strip().lower().rstrip(".")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM whitelist WHERE domain=$1", domain)
    return {"removed": domain}


# ------------------------------- brand anchors -------------------------------

@router.get("/brands")
async def list_brands(
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT domain, brand, category FROM brand_domains ORDER BY brand"
        )
    return {"items": [dict(r) for r in rows]}


@router.post("/brands")
async def add_brand(
    body: BrandEntry,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO brand_domains (domain, brand, category) VALUES ($1, $2, $3)
            ON CONFLICT (domain) DO UPDATE SET brand=EXCLUDED.brand, category=EXCLUDED.category
            """,
            body.domain, body.brand, body.category,
        )
    return {"domain": body.domain, "brand": body.brand}


@router.delete("/brands/{domain}")
async def remove_brand(
    domain: str,
    _: AdminPrincipal = Depends(current_admin),
    pool=Depends(get_pool),
):
    domain = domain.strip().lower().rstrip(".")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM brand_domains WHERE domain=$1", domain)
    return {"removed": domain}


# ------------------------------- test scan -----------------------------------

class ScanRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)


SCANNER_URL = os.getenv("SCANNER_URL", "http://ai_scanner:8090")


@router.post("/scan")
async def admin_scan(
    body: ScanRequest = Body(...),
    _: AdminPrincipal = Depends(current_admin),
):
    """Run a synchronous scan: Playwright fetch + AI verdict + outbound link
    triage. Proxies to the scanner container's internal /scan endpoint."""
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(
                f"{SCANNER_URL}/scan",
                json={"url": body.url},
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.text[:500] or "scanner error",
            )
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(502, f"scanner unreachable: {exc}")
