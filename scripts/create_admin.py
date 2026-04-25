"""Create or reset an admin (or upgrade a user) account.

Usage:
    docker compose exec -T api python -m scripts.create_admin admin@vendly.my
    docker compose exec -T api python -m scripts.create_admin admin@vendly.my --password STRONGPW

Always inserts/updates the row in `users` with role='admin'. Generates an
invite_code + doh_token if missing.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import secrets
import string
import sys

import asyncpg
import bcrypt


INVITE_ALPHABET = string.ascii_uppercase + string.digits


def new_invite_code(length: int = 8) -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))


def new_doh_token() -> str:
    return secrets.token_urlsafe(48)


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.create_admin <email> [--password <pw>]", file=sys.stderr)
        return 2

    email = sys.argv[1].strip().lower()
    pw: str | None = None
    if "--password" in sys.argv:
        pw = sys.argv[sys.argv.index("--password") + 1]
    if not pw:
        pw = getpass.getpass("password: ")
        pw2 = getpass.getpass("repeat:   ")
        if pw != pw2:
            print("passwords differ", file=sys.stderr)
            return 2
    if len(pw) < 10:
        print("password too short (min 10 chars)", file=sys.stderr)
        return 2

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        await conn.execute(
            """
            INSERT INTO users (email, password_hash, role, invite_code, doh_token)
            VALUES ($1, $2, 'admin', $3, $4)
            ON CONFLICT (email) DO UPDATE SET
              password_hash = EXCLUDED.password_hash,
              role = 'admin'
            """,
            email, hashed, new_invite_code(), new_doh_token(),
        )
        print(f"[scamlens] admin ready: {email}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
