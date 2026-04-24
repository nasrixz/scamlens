"""Seed starter blocklist into Postgres.

Usage (from repo root, with Compose stack running):
    docker compose exec -T postgres \\
        psql -U $POSTGRES_USER -d $POSTGRES_DB < scripts/seed_blocklist.sql

Or run this Python file locally against any DATABASE_URL you expose.

We keep a tiny hand-curated starter list here so you can test the DNS pipe
end-to-end without waiting on external feeds. The full loader (pulls URLhaus,
PhishTank, OpenPhish) is wired up during Phase 3 alongside the scanner.
"""
from __future__ import annotations

import asyncio
import os

import asyncpg


STARTER = [
    # Obvious phishing / typosquats to prove the pipeline works.
    ("paypa1.com", "typosquat-paypal"),
    ("faceb00k-login.com", "phish-facebook"),
    ("app1e-support.com", "phish-apple"),
    ("secure-chase-verify.com", "phish-chase"),
    ("amazon-refund-center.com", "phish-amazon"),
    ("crypto-double-reward.com", "scam-crypto"),
    ("netflix-billing-update.com", "phish-netflix"),
    ("micros0ft-security.com", "phish-microsoft"),
    # Canonical test domain — leave this one in, it's how you prove blocking.
    ("scam-test.scamlens.local", "test"),
]


async def main() -> None:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.executemany(
            """
            INSERT INTO blocklist_seed (domain, category)
            VALUES ($1, $2)
            ON CONFLICT (domain) DO NOTHING
            """,
            STARTER,
        )
        count = await conn.fetchval("SELECT count(*) FROM blocklist_seed")
        print(f"[scamlens] blocklist_seed rows: {count}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
