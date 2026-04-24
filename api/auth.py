"""Admin auth — bcrypt password check + JWT session."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status

from .config import Config
from .deps import get_cfg, get_pool


COOKIE_NAME = "scamlens_admin"


@dataclass
class AdminPrincipal:
    id: int
    email: str
    role: str


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def issue_token(cfg: Config, admin_id: int, email: str, role: str) -> str:
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET not configured")
    now = int(time.time())
    payload = {
        "sub": str(admin_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + cfg.jwt_ttl_hours * 3600,
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def decode_token(cfg: Config, token: str) -> AdminPrincipal:
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return AdminPrincipal(
        id=int(payload["sub"]),
        email=payload["email"],
        role=payload.get("role", "admin"),
    )


async def current_admin(
    request: Request,
    cfg: Config = Depends(get_cfg),
    session_cookie: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> AdminPrincipal:
    # Accept either Authorization: Bearer <token> or cookie.
    token = session_cookie
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    return decode_token(cfg, token)


async def fetch_admin_by_email(pool, email: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, password_hash, role FROM admins WHERE email = $1",
            email.lower().strip(),
        )


async def touch_last_login(pool, admin_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE admins SET last_login_at = now() WHERE id = $1", admin_id,
        )
