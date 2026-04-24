"""Core resolution logic: cache → blocklist → forward → maybe-scan."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import structlog
from dnslib import DNSRecord, RR, QTYPE, A, AAAA, RCODE

from .cache import Verdict, VerdictCache, VERDICT_SCAM, VERDICT_SUSPICIOUS
from .config import Config
from .db import Database
from .upstream import UpstreamResolver

log = structlog.get_logger()


# Never scan or block these. Short-circuit to upstream.
BYPASS_SUFFIXES = (
    "in-addr.arpa", "ip6.arpa", "local", "localhost", "arpa",
)


@dataclass
class ResolveResult:
    wire: bytes
    blocked: bool
    domain: str
    verdict: Optional[Verdict]


class Resolver:
    def __init__(
        self,
        config: Config,
        cache: VerdictCache,
        db: Database,
        upstream: UpstreamResolver,
        blocklist: set[str],
    ):
        self._cfg = config
        self._cache = cache
        self._db = db
        self._upstream = upstream
        # Local blocklist seed — instant match, no Redis roundtrip.
        self._blocklist = blocklist

    async def resolve(self, wire: bytes, client_ip: Optional[str]) -> ResolveResult:
        try:
            request = DNSRecord.parse(wire)
        except Exception as exc:
            log.warning("parse_failed", error=str(exc))
            return ResolveResult(wire=_servfail(wire), blocked=False, domain="", verdict=None)

        qname = str(request.q.qname).rstrip(".").lower()
        qtype = QTYPE[request.q.qtype]

        if not qname or _is_bypass(qname):
            return await self._forward(request, wire, qname)

        verdict = await self._lookup(qname)

        if verdict and verdict.is_blocking:
            return self._block(request, qname, qtype, verdict, client_ip)

        # Forward upstream first — user experience beats scanning latency.
        result = await self._forward(request, wire, qname)

        # If we have no verdict at all, schedule an async scan.
        if verdict is None and _looks_scannable(qname, qtype):
            asyncio.create_task(self._enqueue_if_new(qname))

        return result

    async def _lookup(self, domain: str) -> Optional[Verdict]:
        # Walk parent chain: foo.bar.baz.com → bar.baz.com → baz.com.
        for candidate in _parent_chain(domain):
            if candidate in self._blocklist:
                return Verdict(verdict=VERDICT_SCAM, reason="static blocklist", source="blocklist")
            cached = await self._cache.get(candidate)
            if cached is not None:
                return cached
        return None

    def _block(
        self,
        request: DNSRecord,
        domain: str,
        qtype: str,
        verdict: Verdict,
        client_ip: Optional[str],
    ) -> ResolveResult:
        reply = request.reply()
        if qtype == "A":
            reply.add_answer(RR(
                request.q.qname, QTYPE.A,
                rdata=A(self._cfg.block_ip), ttl=self._cfg.block_ttl,
            ))
        elif qtype == "AAAA":
            # No IPv6 sinkhole — answer empty (NOERROR, 0 answers) so clients
            # fall back to the A record (the block page).
            pass
        else:
            # For TXT/MX/etc. respond NXDOMAIN so the query clearly fails.
            reply.header.rcode = RCODE.NXDOMAIN

        asyncio.create_task(self._db.log_block(
            domain=domain,
            reason=verdict.reason or verdict.source,
            verdict=verdict.verdict,
            risk_score=verdict.risk_score,
            confidence=verdict.confidence,
            mimics_brand=None,
            client_ip=client_ip,
        ))
        log.info("blocked", domain=domain, verdict=verdict.verdict, source=verdict.source)
        return ResolveResult(
            wire=reply.pack(), blocked=True, domain=domain, verdict=verdict,
        )

    async def _forward(
        self, request: DNSRecord, wire: bytes, domain: str,
    ) -> ResolveResult:
        answer = await self._upstream.query(wire)
        if answer is None:
            reply = request.reply()
            reply.header.rcode = RCODE.SERVFAIL
            return ResolveResult(wire=reply.pack(), blocked=False, domain=domain, verdict=None)
        return ResolveResult(wire=answer, blocked=False, domain=domain, verdict=None)

    async def _enqueue_if_new(self, domain: str) -> None:
        # Mark pending so repeated queries don't re-enqueue. Rate-limit on top
        # of that so a single popular unknown domain can't hammer the scanner.
        if not await self._cache.rate_limit_ok(domain):
            return
        claimed = await self._cache.mark_pending(domain, ttl=self._cfg.unknown_ttl)
        if claimed:
            await self._cache.enqueue_scan(domain)
            log.info("scan_enqueued", domain=domain)


def _is_bypass(domain: str) -> bool:
    return any(domain == s or domain.endswith("." + s) for s in BYPASS_SUFFIXES)


def _looks_scannable(domain: str, qtype: str) -> bool:
    # Only trigger scans for the typical web lookup types.
    if qtype not in ("A", "AAAA", "HTTPS"):
        return False
    # Ignore single-label names (e.g. "wpad") — they're never real scam sites.
    return "." in domain


def _parent_chain(domain: str):
    """Yield domain, then each parent, stopping before the TLD."""
    parts = domain.split(".")
    # Stop at 2 labels (e.g. "example.com") — no point matching "com".
    for i in range(len(parts) - 1):
        yield ".".join(parts[i:])


def _servfail(wire: bytes) -> bytes:
    try:
        request = DNSRecord.parse(wire)
        reply = request.reply()
        reply.header.rcode = RCODE.SERVFAIL
        return reply.pack()
    except Exception:
        return b""


# Suppress unused-import lint for AAAA (kept for future IPv6 sinkhole).
_ = AAAA
