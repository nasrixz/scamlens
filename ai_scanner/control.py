"""Internal admin/control HTTP endpoint for the scanner.

Exposes POST /scan on port 8090 inside the docker network — the API
container proxies admin "test scan" requests here. Not exposed to the
internet (no nginx vhost).

Returns a full scan report:
  - AI verdict on the main page
  - RDAP age + cached typosquat / blocklist signals
  - PNG screenshot (base64)
  - Truncated HTML
  - Extracted outbound links with cheap per-domain triage
"""
from __future__ import annotations

import base64
import re
from html import unescape
from urllib.parse import urlparse

import structlog
from aiohttp import web

from .ai import AIClient, ScanVerdict
from .config import Config
from .fetcher import PageFetcher
from .heuristics import analyze, render_for_prompt, severity_floor
from .rdap import lookup_age
from .store import VerdictStore

log = structlog.get_logger()

HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def build_app(
    cfg: Config,
    fetcher: PageFetcher,
    ai: AIClient,
    redis,
    store: VerdictStore,
) -> web.Application:
    async def scan(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        url = (body.get("url") or "").strip()
        if not url:
            return web.json_response({"error": "url required"}, status=400)

        domain = _extract_domain(url)
        if not domain:
            return web.json_response({"error": "could not parse domain"}, status=400)

        log.info("admin_scan_start", domain=domain)

        capture = await fetcher.fetch(domain)
        if capture is None:
            return web.json_response({
                "domain": domain,
                "fetched": False,
                "error": "Playwright fetch failed (timeout, DNS, or hostile TLS)",
            })

        # Empty / error / parking-style page → skip AI entirely. Saves a call
        # on dead domains, gives the user a clear signal instead of an AI
        # making up reasons from nothing.
        empty = _classify_empty_page(capture)
        if empty is not None:
            await store.save_error(domain, empty, cfg.unknown_ttl)
            return web.json_response({
                "domain": domain,
                "fetched": True,
                "empty_page": True,
                "empty_reason": empty,
                "final_url": capture.final_url,
                "status": capture.status,
                "title": capture.title,
                "html_excerpt": capture.html[:1000],
                "screenshot_base64": base64.b64encode(capture.screenshot_png).decode(),
                "verdict": None,
                "links": [],
            })

        heuristics = analyze(capture.html, domain)
        verdict = await ai.scan(
            domain=domain,
            html=capture.html,
            screenshot_png=capture.screenshot_png,
            heuristic_summary=render_for_prompt(heuristics),
        )
        verdict = _apply_floor(verdict, heuristics, domain)
        # Persist same as worker does so future DNS hits skip the rescan.
        await store.save(
            domain=domain, verdict=verdict,
            safe_ttl=cfg.safe_ttl, scam_ttl=cfg.scam_ttl,
            unknown_ttl=cfg.unknown_ttl,
        )

        age = await lookup_age(domain, redis)

        # Triage outbound links — cheap signals only.
        links = _extract_links(capture.html, capture.final_url)
        triaged = await _triage_links(links, redis)

        return web.json_response({
            "domain": domain,
            "fetched": True,
            "final_url": capture.final_url,
            "status": capture.status,
            "title": capture.title,
            "html_excerpt": capture.html[:8000],
            "screenshot_base64": base64.b64encode(capture.screenshot_png).decode(),
            "verdict": {
                "verdict": verdict.verdict,
                "risk_score": verdict.risk_score,
                "confidence": verdict.confidence,
                "reasons": verdict.reasons,
                "mimics_brand": verdict.mimics_brand,
                "model": verdict.model,
            },
            "domain_age_days": age.days,
            "links": triaged,
        })

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/scan", scan)
    app.router.add_get("/health", health)
    return app


# ----------------- helpers --------------------------------------------------

def _apply_floor(verdict: ScanVerdict, heuristics, domain: str) -> ScanVerdict:
    rank = {"safe": 0, "suspicious": 1, "scam": 2}
    floor_v, floor_r = severity_floor(heuristics, domain)
    if rank[floor_v] <= rank[verdict.verdict]:
        return verdict
    bump = {"suspicious": 65, "scam": 90}[floor_v]
    return ScanVerdict(
        verdict=floor_v,
        risk_score=max(verdict.risk_score, bump),
        confidence=max(verdict.confidence, 70),
        reasons=verdict.reasons + floor_r + ["promoted by static-scan heuristics"],
        mimics_brand=verdict.mimics_brand,
        model=verdict.model,
    )


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _visible_text(html: str) -> str:
    """Quick + cheap text extraction. Strips tags, normalizes whitespace.
    Doesn't need to be perfect — used only to detect 'page is empty'."""
    no_script = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = _TAG_RE.sub(" ", no_script)
    text = unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _classify_empty_page(capture) -> str | None:
    """Return a human-readable reason if the page has no scannable content,
    otherwise None."""
    status = capture.status or 0
    if status >= 400:
        return f"Server returned HTTP {status}"
    text = _visible_text(capture.html)
    # Fewer than this many visible chars means there's nothing for the AI
    # to read — likely a blank holding page, a JS shell that didn't render,
    # or a parking page redirected away.
    if len(text) < 60:
        return "Page is empty (no visible text)"
    if len(capture.html) < 200:
        return "Page returned no HTML body"
    # Common parking-domain keywords (very loose check, on tiny pages).
    if len(text) < 400:
        lowered = text.lower()
        if any(k in lowered for k in (
            "domain is for sale",
            "buy this domain",
            "this domain is parked",
            "default web page",
            "404 not found",
            "site temporarily unavailable",
        )):
            return "Domain parking / placeholder page"
    return None


def _extract_domain(url_or_domain: str) -> str:
    s = url_or_domain.strip()
    if not s.startswith(("http://", "https://")):
        s = "http://" + s
    try:
        parsed = urlparse(s)
        host = (parsed.hostname or "").lower()
        return host
    except Exception:
        return ""


def _extract_links(html: str, base_url: str) -> list[str]:
    """Pull href values out of HTML (regex — good enough, no parser needed)."""
    seen: set[str] = set()
    results: list[str] = []
    for m in HREF_RE.findall(html):
        href = m.strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
            continue
        # Relative → join with base
        if href.startswith("/") or not href.startswith(("http://", "https://")):
            try:
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            except Exception:
                continue
        if href in seen:
            continue
        seen.add(href)
        results.append(href)
        if len(results) >= 200:
            break
    return results


async def _triage_links(links: list[str], redis) -> list[dict]:
    """For each unique external domain on the page, attach a cached verdict
    if we already have one in Redis. Capped at 30 domains."""
    import json as _json
    by_domain: dict[str, str] = {}
    for href in links:
        d = _extract_domain(href)
        if not d:
            continue
        by_domain.setdefault(d, href)
        if len(by_domain) >= 30:
            break

    out: list[dict] = []
    for d, href in by_domain.items():
        raw = await redis.get(f"verdict:{d}")
        verdict = None
        if raw:
            try:
                v = _json.loads(raw)
                verdict = {
                    "verdict": v.get("verdict"),
                    "risk_score": v.get("risk_score"),
                    "source": v.get("source"),
                }
            except Exception:
                pass
        out.append({
            "domain": d,
            "first_seen_href": href,
            "cached_verdict": verdict,
        })
    # Risky-first: scam/suspicious cached → top
    rank = {"scam": 0, "suspicious": 1, "pending": 2}
    out.sort(key=lambda r: rank.get(
        (r["cached_verdict"] or {}).get("verdict", ""), 9,
    ))
    return out
