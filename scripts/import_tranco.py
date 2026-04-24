"""Import the Tranco top-N popular domains into the whitelist.

Tranco is a research list (https://tranco-list.eu) — ranked by cross-engine
popularity. Top 10k covers >99% of real-world user traffic. Import as a
bulk 'popularity' whitelist so ScamLens skips AI scans on well-known sites.

Usage (from repo root, stack running):
    docker compose exec -T api python -m scripts.import_tranco --top 10000

Caveats:
  * Overwrites the 'popularity' rows but leaves manual admin entries alone.
  * You can re-run whenever — refresh weekly is plenty.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import os
import sys
import zipfile

import asyncpg
import httpx


TRANCO_LATEST = "https://tranco-list.eu/top-1m.csv.zip"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10000, help="Import top N domains")
    ap.add_argument("--url", default=TRANCO_LATEST)
    args = ap.parse_args()

    print(f"[scamlens] downloading Tranco list…", file=sys.stderr)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(args.url, follow_redirects=True)
        resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name).decode()

    rows = []
    for line in io.StringIO(raw):
        rank, domain = line.strip().split(",", 1)
        rows.append((domain.lower(), f"tranco-rank-{rank}"))
        if len(rows) >= args.top:
            break

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        # Remove stale popularity rows, keep manual ones.
        await conn.execute(
            "DELETE FROM whitelist WHERE reason LIKE 'tranco-rank-%'"
        )
        await conn.executemany(
            """
            INSERT INTO whitelist (domain, reason, added_by)
            VALUES ($1, $2, 'tranco')
            ON CONFLICT (domain) DO NOTHING
            """,
            rows,
        )
        count = await conn.fetchval("SELECT count(*) FROM whitelist")
        print(f"[scamlens] whitelist rows total: {count}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
