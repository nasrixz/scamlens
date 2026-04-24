"""Create or reset an admin account.

Usage (from repo root, stack running):
    docker compose exec -T api python -m scripts.create_admin admin@vendly.my

You'll be prompted for a password. Script upserts the user into `admins`
with a bcrypt hash.

Run again with the same email to reset the password.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import sys

import asyncpg
import bcrypt


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
            INSERT INTO admins (email, password_hash, role)
            VALUES ($1, $2, 'admin')
            ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            email, hashed,
        )
        print(f"[scamlens] admin ready: {email}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
