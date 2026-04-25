"""Internal HTTP control plane for manual scrape triggers.

Listens on :8091 inside the docker network. The API container's admin
proxy talks to /run. Concurrency limited to one scrape at a time via a
Redis lock so the Threads token isn't burned twice and the cron + manual
loops don't collide.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import structlog
from aiohttp import web

from .config import Config
from .extract import extract_urls
from .threads_client import ThreadsClient
from .worker import ScrapeWorker

log = structlog.get_logger()

LOCK_KEY = "scrape_lock:threads"
LOCK_TTL = 90 * 60   # 1.5h — covers the longest reasonable manual run


def build_app(cfg: Config, worker: ScrapeWorker, redis) -> web.Application:
    async def run_handler(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            body = {}

        keywords: Optional[list[str]] = body.get("keywords")
        duration_min = body.get("duration_minutes")
        max_pages = body.get("max_pages")

        if not cfg.threads_token:
            return web.json_response(
                {"error": "THREADS_ACCESS_TOKEN not configured on the scraper"},
                status=503,
            )

        claimed = await redis.set(LOCK_KEY, "manual", ex=LOCK_TTL, nx=True)
        if not claimed:
            return web.json_response(
                {"status": "busy", "message": "A scrape is already running"},
                status=409,
            )

        # Run in background — admin polls /api/admin/scrape/status
        # and inspects scrape_runs in DB for results.
        asyncio.create_task(_run_safely(
            worker, redis,
            keywords=keywords,
            duration_min=duration_min,
            max_pages=max_pages,
        ))
        return web.json_response({"status": "started"})

    async def status_handler(_: web.Request) -> web.Response:
        running = bool(await redis.get(LOCK_KEY))
        return web.json_response({"running": running})

    async def search_handler(request: web.Request) -> web.Response:
        """Debug helper: run a keyword search and return raw posts +
        URLs we'd extract. Doesn't touch the scanner or DB."""
        if not cfg.threads_token:
            return web.json_response({"error": "no token"}, status=503)
        try:
            body = await request.json()
        except Exception:
            body = {}
        q = (body.get("q") or "scam").strip()
        max_pages = int(body.get("max_pages") or 1)

        client = ThreadsClient(cfg.threads_token, search_type=cfg.threads_search_type)
        out: list[dict] = []
        async for post in client.keyword_search(q, max_pages=max_pages, page_delay=0.5):
            urls = extract_urls(post.text)
            out.append({
                "id": post.id,
                "username": post.username,
                "permalink": post.permalink,
                "media_type": post.media_type,
                "is_reply": post.is_reply,
                "is_quote_post": post.is_quote_post,
                "text_preview": post.text[:280],
                "extracted_urls": urls,
            })
        return web.json_response({"q": q, "count": len(out), "posts": out})

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/run", run_handler)
    app.router.add_get("/status", status_handler)
    app.router.add_post("/search", search_handler)
    app.router.add_get("/health", health)
    return app


async def _run_safely(
    worker: ScrapeWorker,
    redis,
    keywords: Optional[list[str]],
    duration_min: Optional[int],
    max_pages: Optional[int],
) -> None:
    try:
        log.info(
            "manual_scrape_start",
            keywords=(keywords or "default"),
            duration_min=duration_min,
        )
        await worker.run_window(
            keywords=[k.strip() for k in keywords if k.strip()] if keywords else None,
            duration_minutes=duration_min,
            max_pages=max_pages,
        )
    except Exception as exc:
        log.exception("manual_scrape_failed", error=str(exc))
    finally:
        await redis.delete(LOCK_KEY)
