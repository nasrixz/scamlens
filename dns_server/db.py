"""Postgres pool + write helpers for DNS server.

DNS hot path must NOT block on the DB — callers fire-and-forget via
`asyncio.create_task(db.log_block(...))`.
"""
from __future__ import annotations

from typing import Optional

import asyncpg
import structlog

log = structlog.get_logger()


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=1, max_size=5, command_timeout=5
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def load_blocklist(self) -> list[str]:
        """Return all known scam domains from blocklist_seed + confirmed reports."""
        if not self._pool:
            return []
        rows = await self._pool.fetch(
            """
            SELECT domain FROM blocklist_seed
            UNION
            SELECT domain FROM domain_verdicts WHERE verdict IN ('scam', 'suspicious')
            UNION
            SELECT domain FROM user_reports WHERE status = 'confirmed'
            """
        )
        return [r["domain"] for r in rows]

    async def load_whitelist(self) -> list[str]:
        """Domains that should skip all checks + AI scans."""
        if not self._pool:
            return []
        try:
            rows = await self._pool.fetch("SELECT domain FROM whitelist")
            return [r["domain"] for r in rows]
        except Exception:
            # Table may not exist yet on older deployments.
            return []

    async def promote_to_blocklist(self, domain: str, category: str) -> None:
        """Insert into blocklist_seed if not already present. Fire-and-forget
        from the DNS hot path."""
        if not self._pool:
            return
        try:
            await self._pool.execute(
                """
                INSERT INTO blocklist_seed (domain, category)
                VALUES ($1, $2)
                ON CONFLICT (domain) DO NOTHING
                """,
                domain, category,
            )
        except Exception as exc:
            log.warning("promote_blocklist_failed", domain=domain, error=str(exc))

    async def load_brand_domains(self) -> list[tuple[str, str]]:
        """(domain, brand) rows for typosquat detection."""
        if not self._pool:
            return []
        try:
            rows = await self._pool.fetch(
                "SELECT domain, brand FROM brand_domains"
            )
            return [(r["domain"], r["brand"]) for r in rows]
        except Exception:
            return []

    async def log_block(
        self,
        domain: str,
        reason: str,
        verdict: str,
        risk_score: int,
        confidence: int,
        mimics_brand: Optional[str],
        client_ip: Optional[str],
        resolved_ip: Optional[str] = None,
    ) -> None:
        if not self._pool:
            return
        try:
            await self._pool.execute(
                """
                INSERT INTO blocked_attempts
                  (domain, reason, verdict, risk_score, ai_confidence,
                   mimics_brand, client_ip, resolved_ip)
                VALUES ($1, $2, $3, $4, $5, $6, $7::inet, $8::inet)
                """,
                domain, reason, verdict, risk_score, confidence,
                mimics_brand, client_ip, resolved_ip,
            )
        except Exception as exc:
            log.warning("log_block_failed", domain=domain, error=str(exc))
