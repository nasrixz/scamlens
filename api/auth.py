"""Authentication for both regular users and admins.

One `users` table. Role-based access for admin endpoints. JWT in an
HttpOnly cookie. Helper generators produce the friendly invite code
and the per-user DoH token.
"""
from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass
from typing import Optional

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status

from .config import Config
from .deps import get_cfg, get_pool


COOKIE_NAME = "scamlens_session"
INVITE_ALPHABET = string.ascii_uppercase + string.digits  # human-friendly


@dataclass
class Principal:
    id: int
    email: str
    role: str
    invite_code: str
    doh_token: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# ----------------------------- crypto helpers -------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def new_invite_code(length: int = 8) -> str:
    """e.g. 'A4B9XK7Q' — easy to read aloud, hard to guess."""
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))


def new_doh_token() -> str:
    """48-char hex (DNS-label safe) for per-user DoH subdomain."""
    return secrets.token_hex(24)


# ----------------------------- jwt helpers ----------------------------------

def issue_token(cfg: Config, user_id: int, email: str, role: str) -> str:
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET not configured")
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + cfg.jwt_ttl_hours * 3600,
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def decode_token(cfg: Config, token: str) -> dict:
    try:
        return jwt.decode(token, cfg.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")


# ----------------------------- DB lookups -----------------------------------

async def fetch_by_email(pool, email: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, password_hash, role, invite_code, doh_token "
            "FROM users WHERE email = $1",
            email.lower().strip(),
        )


async def fetch_by_id(pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, email, role, invite_code, doh_token "
            "FROM users WHERE id = $1",
            user_id,
        )


async def touch_last_login(pool, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET last_login_at = now() WHERE id = $1", user_id,
        )


# ----------------------------- principals -----------------------------------

async def current_principal(
    request: Request,
    cfg: Config = Depends(get_cfg),
    pool=Depends(get_pool),
    session_cookie: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> Principal:
    token = session_cookie
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    payload = decode_token(cfg, token)
    user_id = int(payload["sub"])
    row = await fetch_by_id(pool, user_id)
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return Principal(
        id=row["id"],
        email=row["email"],
        role=row["role"],
        invite_code=row["invite_code"],
        doh_token=row["doh_token"],
    )


async def current_admin(who: Principal = Depends(current_principal)) -> Principal:
    if not who.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return who
