"""Core resolution logic.

Pipeline (ordered by cost):
  1. Bypass suffixes (.arpa / .local / .localhost) → forward upstream.
  2. Whitelist (exact or parent match) → forward upstream, skip scan.
  3. Blacklist (exact or parent match) → sinkhole to BLOCK_PAGE_IP.
  4. Redis verdict cache (scan or prior verdict) → honour it.
  5. Typosquat detector against brand anchors → sinkhole with brand mimic.
  6. Truly unknown → forward + enqueue AI scan.

Hot path never blocks on DB; all logging fire-and-forget.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import structlog
from dnslib import DNSRecord, RR, QTYPE, A, AAAA, RCODE, DNSQuestion

from .cache import Verdict, VerdictCache, VERDICT_SCAM
from .config import Config
from .db import Database
from .typosquat import TyposquatDetector, TyposquatHit
from .upstream import UpstreamResolver

log = structlog.get_logger()


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
        whitelist: set[str],
        typosquat: TyposquatDetector,
    ):
        self._cfg = config
        self._cache = cache
        self._db = db
        self._upstream = upstream
        self._blocklist = blocklist
        self._whitelist = whitelist
        self._typosquat = typosquat

    async def resolve(
        self,
        wire: bytes,
        client_ip: Optional[str],
        user_id: Optional[int] = None,
    ) -> ResolveResult:
        try:
            request = DNSRecord.parse(wire)
        except Exception as exc:
            log.warning("parse_failed", error=str(exc))
            return ResolveResult(wire=_servfail(wire), blocked=False, domain="", verdict=None)

        qname = str(request.q.qname).rstrip(".").lower()
        qtype = QTYPE[request.q.qtype]

        if not qname or _is_bypass(qname):
            return await self._forward(request, wire, qname)

        # 1) Whitelist → forward, no scan.
        if self._match_chain(qname, self._whitelist):
            return await self._forward(request, wire, qname)

        # 2) Blacklist (static seed + confirmed reports + AI 'scam' verdicts).
        if self._match_chain(qname, self._blocklist):
            verdict = Verdict(
                verdict=VERDICT_SCAM, reason="blocklist", source="blocklist",
            )
            return self._block(request, qname, qtype, verdict, client_ip, user_id)

        # 3) Redis cache hit (scanner verdict or short-lived pending marker).
        cached = await self._cache_lookup(qname)
        if cached and cached.is_blocking:
            return self._block(request, qname, qtype, cached, client_ip, user_id)
        if cached and cached.verdict == "safe":
            return await self._forward(request, wire, qname)

        # 4) Typosquat — cheap, deterministic, no AI call.
        hit = self._typosquat.check(qname)
        if hit is not None:
            verdict = Verdict(
                verdict=VERDICT_SCAM,
                reason=hit.reason,
                source="typosquat",
                confidence=85 if hit.distance == 0 else 70,
                risk_score=90 if hit.distance == 0 else 75,
            )
            asyncio.create_task(
                self._cache.set(qname, verdict, ttl=self._cfg.scam_ttl)
            )
            return self._block_with_brand(request, qname, qtype, verdict, hit, client_ip, user_id)

        # 5) Forward first — no delay to user — then trigger scan.
        result = await self._forward(request, wire, qname)
        if cached is None and _looks_scannable(qname, qtype):
            asyncio.create_task(self._enqueue_if_new(qname))
        return result

    # ---- helpers -----------------------------------------------------------

    def _match_chain(self, domain: str, s: set[str]) -> bool:
        for candidate in _parent_chain(domain):
            if candidate in s:
                return True
        return False

    async def _cache_lookup(self, domain: str) -> Optional[Verdict]:
        for candidate in _parent_chain(domain):
            v = await self._cache.get(candidate)
            if v is not None:
                return v
        return None

    def _block(
        self,
        request: DNSRecord,
        domain: str,
        qtype: str,
        verdict: Verdict,
        client_ip: Optional[str],
        user_id: Optional[int] = None,
    ) -> ResolveResult:
        reply = request.reply()
        if qtype == "A":
            reply.add_answer(RR(
                request.q.qname, QTYPE.A,
                rdata=A(self._cfg.block_ip), ttl=self._cfg.block_ttl,
            ))
        elif qtype == "AAAA":
            pass
        else:
            reply.header.rcode = RCODE.NXDOMAIN

        asyncio.create_task(self._resolve_then_log(
            domain=domain,
            reason=verdict.reason or verdict.source,
            verdict=verdict.verdict,
            risk_score=verdict.risk_score,
            confidence=verdict.confidence,
            mimics_brand=None,
            client_ip=client_ip,
            user_id=user_id,
        ))
        # Every block must end up visible in the admin Blocklist tab so the
        # operator can audit + override via whitelist. Source 'blocklist'
        # already came from blocklist_seed; everything else (cache/ai/etc.)
        # gets promoted with a descriptive category.
        if verdict.source != "blocklist":
            asyncio.create_task(
                self._db.promote_to_blocklist(domain, _category_for(verdict))
            )
        log.info("blocked", domain=domain, verdict=verdict.verdict, source=verdict.source)
        return ResolveResult(
            wire=reply.pack(), blocked=True, domain=domain, verdict=verdict,
        )

    def _block_with_brand(
        self,
        request: DNSRecord,
        domain: str,
        qtype: str,
        verdict: Verdict,
        hit: TyposquatHit,
        client_ip: Optional[str],
        user_id: Optional[int] = None,
    ) -> ResolveResult:
        reply = request.reply()
        if qtype == "A":
            reply.add_answer(RR(
                request.q.qname, QTYPE.A,
                rdata=A(self._cfg.block_ip), ttl=self._cfg.block_ttl,
            ))
        elif qtype == "AAAA":
            pass
        else:
            reply.header.rcode = RCODE.NXDOMAIN

        asyncio.create_task(self._resolve_then_log(
            domain=domain,
            reason=verdict.reason,
            verdict=verdict.verdict,
            risk_score=verdict.risk_score,
            confidence=verdict.confidence,
            mimics_brand=hit.brand,
            client_ip=client_ip,
            user_id=user_id,
        ))
        # Make typosquat hits visible in the admin Blocklist tab so the
        # operator can audit + remove false positives. Fire-and-forget.
        asyncio.create_task(
            self._db.promote_to_blocklist(domain, f"typosquat-{hit.brand}")
        )
        log.info(
            "blocked_typosquat",
            domain=domain,
            mimics=hit.brand,
            official=hit.brand_domain,
            distance=hit.distance,
        )
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
        if not await self._cache.rate_limit_ok(domain):
            return
        claimed = await self._cache.mark_pending(domain, ttl=self._cfg.unknown_ttl)
        if claimed:
            await self._cache.enqueue_scan(domain)
            log.info("scan_enqueued", domain=domain)

    async def _resolve_then_log(self, **kwargs) -> None:
        """Resolve the scam domain via upstream so the block log captures
        the real IP it would have pointed at. Runs in a background task —
        never blocks the DNS reply path. Also publishes a 'block_event'
        Redis pubsub message so the API can fan out push + SSE."""
        domain = kwargs["domain"]
        ip = await self._resolve_scam_ip(domain)
        await self._db.log_block(resolved_ip=ip, **kwargs)
        if ip:
            log.info("blocked_resolved", domain=domain, resolved_ip=ip)

        user_id = kwargs.get("user_id")
        if user_id is not None:
            try:
                payload = {
                    "user_id": user_id,
                    "domain": domain,
                    "reason": kwargs.get("reason"),
                    "verdict": kwargs.get("verdict"),
                    "risk_score": kwargs.get("risk_score"),
                    "confidence": kwargs.get("confidence"),
                    "mimics_brand": kwargs.get("mimics_brand"),
                    "resolved_ip": ip,
                }
                import json as _json
                await self._cache._redis.publish(
                    "scamlens:block_events", _json.dumps(payload),
                )
            except Exception as exc:
                log.warning("publish_failed", error=str(exc)[:160])

    async def _resolve_scam_ip(self, domain: str) -> Optional[str]:
        """Issue an A query upstream for the blocked domain and return the
        first A record. Returns None on failure. Bounded by upstream timeout."""
        try:
            q = DNSRecord(q=DNSQuestion(domain, QTYPE.A))
            answer = await self._upstream.query(q.pack())
            if not answer:
                return None
            reply = DNSRecord.parse(answer)
            for rr in reply.rr:
                if rr.rtype == QTYPE.A:
                    return str(rr.rdata)
        except Exception as exc:
            log.info("resolve_scam_ip_failed", domain=domain, error=str(exc)[:120])
        return None


def _category_for(verdict: Verdict) -> str:
    """Map a verdict to a blocklist_seed category. Keeps audit trail readable."""
    src = (verdict.source or "").lower()
    if src == "ai":
        return "ai-confirmed"
    if src == "scan_error":
        return "ai-scan-error"
    if src == "typosquat":
        return "typosquat"
    if src == "cache":
        # Older cached verdicts that lost their original source label.
        return f"cache-{verdict.verdict}"
    if src == "user_report":
        return "user-report"
    return src or "auto"


def _is_bypass(domain: str) -> bool:
    return any(domain == s or domain.endswith("." + s) for s in BYPASS_SUFFIXES)


def _looks_scannable(domain: str, qtype: str) -> bool:
    if qtype not in ("A", "AAAA", "HTTPS"):
        return False
    return "." in domain


def _parent_chain(domain: str):
    parts = domain.split(".")
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


_ = AAAA
