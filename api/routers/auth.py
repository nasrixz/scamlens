"""/api/auth/* — registration + login for end users."""
from __future__ import annotations

import re

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from ..auth import (
    COOKIE_NAME,
    Principal,
    current_principal,
    fetch_by_email,
    hash_password,
    issue_token,
    new_doh_token,
    new_invite_code,
    touch_last_login,
    verify_password,
)
from ..deps import get_cfg, get_pool
from ..rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=200)
    display_name: str | None = Field(None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _set_session_cookie(response: Response, token: str, ttl_hours: int) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=ttl_hours * 3600,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/register")
@limiter.limit("10/hour")
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest = Body(...),
    cfg=Depends(get_cfg),
    pool=Depends(get_pool),
):
    """Self-service signup. Generates invite_code + doh_token. No email
    verification in v1. Logs the user in on success."""
    email = body.email.lower().strip()
    existing = await fetch_by_email(pool, email)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    # Re-roll if an invite-code collision happens (8-char base32 → 1.1T space).
    for _ in range(5):
        invite = new_invite_code()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, password_hash, role, invite_code,
                                   doh_token, display_name)
                VALUES ($1, $2, 'user', $3, $4, $5)
                ON CONFLICT (invite_code) DO NOTHING
                RETURNING id, email, role, invite_code, doh_token
                """,
                email, hash_password(body.password), invite,
                new_doh_token(), body.display_name,
            )
        if row:
            token = issue_token(cfg, row["id"], row["email"], row["role"])
            _set_session_cookie(response, token, cfg.jwt_ttl_hours)
            return {
                "id": row["id"],
                "email": row["email"],
                "role": row["role"],
                "invite_code": row["invite_code"],
                "doh_token": row["doh_token"],
            }
    raise HTTPException(500, "could not allocate invite code")


@router.post("/login")
@limiter.limit("30/hour")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest = Body(...),
    cfg=Depends(get_cfg),
    pool=Depends(get_pool),
):
    user = await fetch_by_email(pool, body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = issue_token(cfg, user["id"], user["email"], user["role"])
    await touch_last_login(pool, user["id"])
    _set_session_cookie(response, token, cfg.jwt_ttl_hours)
    return {
        "email": user["email"],
        "role": user["role"],
        "invite_code": user["invite_code"],
    }


@router.post("/logout")
async def logout(response: Response, _=Depends(current_principal)):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(who: Principal = Depends(current_principal)):
    return {
        "id": who.id,
        "email": who.email,
        "role": who.role,
        "invite_code": who.invite_code,
        "doh_token": who.doh_token,
    }
