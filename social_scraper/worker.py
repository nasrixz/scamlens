"""Per-keyword scrape pass: pull posts → extract URLs → classify → block.

Supports three sources:
  threads — Threads keyword search (requires App Review for public results)
  reddit  — Reddit JSON search (free, no auth)
  urlhaus — abuse.ch curated malicious-URL feed (no AI scan needed)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import asyncpg
import httpx
import structlog
from redis.asyncio import Redis

from .config import Config
from .extract import extract_urls, url_to_domain
from .reddit_client import RedditClient, RedditPost
from .threads_client import ThreadsClient, ThreadsPost
from .urlhaus_client import URLhausClient

log = structlog.get_logger()


@dataclass
class RunStats:
    posts_seen: int = 0
    urls_seen: int = 0
    domains_new: int = 0
    domains_blocked: int = 0
    errors: int = 0


class ScrapeWorker:
    def __init__(self, cfg: Config, pool: asyncpg.Pool, redis: Redis, client: ThreadsClient):
        self._cfg = cfg
        self._pool = pool
        self._redis = redis
        self._client = client
        self._reddit = RedditClient()
        self._urlhaus = URLhausClient()

    async def run_window(
        self,
        source: str = "threads",
        keywords: list[str] | None = None,
        duration_minutes: int | None = None,
        max_pages: int | None = None,
        subreddits: list[str] | None = None,
    ) -> RunStats:
        """Dispatch to the named source. `source` ∈ {threads, reddit, urlhaus}.
        Optional overrides let admin /run trigger custom-scoped passes."""
        if source == "urlhaus":
            return await self._run_urlhaus()
        if source == "reddit":
            return await self._run_reddit(keywords, duration_minutes, max_pages, subreddits)
        return await self._run_threads(keywords, duration_minutes, max_pages)

    async def _run_threads(
        self,
        keywords: list[str] | None,
        duration_minutes: int | None,
        max_pages: int | None,
    ) -> RunStats:
        kws = keywords if keywords is not None else self._cfg.keywords
        budget_min = duration_minutes if duration_minutes is not None else self._cfg.duration_minutes
        pages = max_pages if max_pages is not None else self._cfg.max_pages_per_keyword

        stats = RunStats()
        deadline = time.time() + budget_min * 60
        run_id = await self._start_run("threads")

        try:
            for keyword in kws:
                if time.time() >= deadline:
                    break
                log.info("scrape_keyword_start", source="threads", keyword=keyword)
                try:
                    async for post in self._client.keyword_search(
                        keyword,
                        max_pages=pages,
                        page_delay=self._cfg.request_delay_seconds,
                    ):
                        if time.time() >= deadline:
                            break
                        stats.posts_seen += 1
                        await self._handle_post(post, stats)
                except Exception as exc:
                    log.warning("scrape_keyword_failed", keyword=keyword, error=str(exc)[:200])
                    stats.errors += 1
        finally:
            await self._finish_run(run_id, stats)
        log.info("scrape_window_done", source="threads", **stats.__dict__)
        return stats

    async def _run_reddit(
        self,
        keywords: list[str] | None,
        duration_minutes: int | None,
        max_pages: int | None,
        subreddits: list[str] | None,
    ) -> RunStats:
        kws = keywords if keywords is not None else self._cfg.keywords
        budget_min = duration_minutes if duration_minutes is not None else self._cfg.duration_minutes
        pages = max_pages if max_pages is not None else self._cfg.max_pages_per_keyword

        stats = RunStats()
        deadline = time.time() + budget_min * 60
        run_id = await self._start_run("reddit")

        try:
            for keyword in kws:
                if time.time() >= deadline:
                    break
                log.info("scrape_keyword_start", source="reddit", keyword=keyword)
                try:
                    async for post in self._reddit.search(
                        keyword,
                        subreddits=subreddits,
                        max_pages=pages,
                        page_delay=self._cfg.request_delay_seconds,
                    ):
                        if time.time() >= deadline:
                            break
                        stats.posts_seen += 1
                        await self._handle_reddit_post(post, stats)
                except Exception as exc:
                    log.warning("reddit_search_failed", keyword=keyword, error=str(exc)[:200])
                    stats.errors += 1
        finally:
            await self._finish_run(run_id, stats)
        log.info("scrape_window_done", source="reddit", **stats.__dict__)
        return stats

    async def _run_urlhaus(self) -> RunStats:
        stats = RunStats()
        run_id = await self._start_run("urlhaus")
        try:
            async for entry in self._urlhaus.recent():
                stats.urls_seen += 1
                domain = url_to_domain(entry.url)
                if not domain or "." not in domain:
                    continue
                if await self._already_known(domain):
                    continue
                stats.domains_new += 1
                # URLhaus has already classified — promote without AI.
                await self._promote_to_blocklist(
                    domain=domain,
                    source_post=entry.reference or entry.url,
                    platform="urlhaus",
                    reason=[entry.threat or "urlhaus-flagged"],
                )
                stats.domains_blocked += 1
        except Exception as exc:
            log.warning("urlhaus_failed", error=str(exc)[:200])
            stats.errors += 1
        finally:
            await self._finish_run(run_id, stats)
        log.info("scrape_window_done", source="urlhaus", **stats.__dict__)
        return stats

    async def _handle_post(self, post: ThreadsPost, stats: RunStats) -> None:
        # Skip pure replies and quote posts — they piggy-back context from
        # the parent thread and often don't carry their own link. We focus
        # on top-level posts where a scammer drops their domain in plain text.
        if post.is_reply or post.is_quote_post:
            return
        urls = extract_urls(post.text)
        if not urls:
            return
        for url in urls:
            stats.urls_seen += 1
            domain = url_to_domain(url)
            if not domain or "." not in domain:
                continue

            # Skip if we've ALREADY decided about this domain (any direction).
            if await self._already_known(domain):
                continue

            stats.domains_new += 1
            verdict = await self._classify(url)
            if not verdict:
                continue
            v = verdict.get("verdict", {}) or {}
            if (v.get("verdict") == "scam"
                    and (v.get("confidence") or 0) >= self._cfg.confidence_threshold):
                await self._promote_to_blocklist(
                    domain=domain,
                    source_post=post.permalink,
                    platform="threads",
                    reason=v.get("reasons") or [],
                )
                stats.domains_blocked += 1

    async def _handle_reddit_post(self, post: RedditPost, stats: RunStats) -> None:
        """Reddit posts have two URL sources: the `url` field (the external
        link the OP posted, often the actual scam) and `selftext` (markdown
        body that may also contain links)."""
        candidates: list[str] = []
        # Self-post 'url' just points back to reddit.com — skip those.
        if post.url and "reddit.com" not in (post.url or ""):
            candidates.append(post.url)
        candidates.extend(extract_urls(post.title))
        candidates.extend(extract_urls(post.selftext))

        # Dedupe.
        seen: set[str] = set()
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            stats.urls_seen += 1
            domain = url_to_domain(url)
            if not domain or "." not in domain:
                continue
            if await self._already_known(domain):
                continue
            stats.domains_new += 1
            verdict = await self._classify(url)
            if not verdict:
                continue
            v = verdict.get("verdict", {}) or {}
            if (v.get("verdict") == "scam"
                    and (v.get("confidence") or 0) >= self._cfg.confidence_threshold):
                await self._promote_to_blocklist(
                    domain=domain,
                    source_post=post.permalink,
                    platform="reddit",
                    reason=v.get("reasons") or [],
                )
                stats.domains_blocked += 1

    async def _already_known(self, domain: str) -> bool:
        """Already in blocklist OR whitelist OR in Redis verdict cache?"""
        cached = await self._redis.get(f"verdict:{domain}")
        if cached:
            return True
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM blocklist_seed WHERE domain=$1 "
                "UNION ALL SELECT 1 FROM whitelist WHERE domain=$1 LIMIT 1",
                domain,
            )
        return bool(row)

    async def _classify(self, url: str) -> dict | None:
        """Call the scanner /scan endpoint synchronously. Scanner does fetch
        + AI + heuristic floor and returns the full report."""
        try:
            async with httpx.AsyncClient(timeout=90) as c:
                r = await c.post(
                    f"{self._cfg.scanner_url}/scan",
                    json={"url": url},
                )
            if r.status_code != 200:
                log.info("classify_http", url=url, status=r.status_code)
                return None
            return r.json()
        except Exception as exc:
            log.warning("classify_failed", url=url, error=str(exc)[:200])
            return None

    async def _promote_to_blocklist(
        self,
        domain: str,
        source_post: str,
        platform: str,
        reason: list[str],
    ) -> None:
        category = "scraped-" + platform
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO blocklist_seed
                      (domain, category, source_post, source_platform)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (domain) DO UPDATE SET
                      source_post     = COALESCE(blocklist_seed.source_post, EXCLUDED.source_post),
                      source_platform = COALESCE(blocklist_seed.source_platform, EXCLUDED.source_platform)
                    """,
                    domain, category, source_post, platform,
                )
            log.info(
                "scrape_blocked",
                domain=domain,
                source=source_post,
                reasons=reason[:3],
            )
        except Exception as exc:
            log.warning("scrape_block_failed", domain=domain, error=str(exc)[:200])

    async def _start_run(self, platform: str) -> int | None:
        try:
            async with self._pool.acquire() as conn:
                return await conn.fetchval(
                    "INSERT INTO scrape_runs (platform) VALUES ($1) RETURNING id",
                    platform,
                )
        except Exception:
            return None

    async def _finish_run(self, run_id: int | None, stats: RunStats) -> None:
        if not run_id:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE scrape_runs
                    SET finished_at = now(),
                        posts_seen = $2,
                        urls_seen = $3,
                        domains_new = $4,
                        domains_blocked = $5,
                        errors = $6
                    WHERE id = $1
                    """,
                    run_id,
                    stats.posts_seen,
                    stats.urls_seen,
                    stats.domains_new,
                    stats.domains_blocked,
                    stats.errors,
                )
        except Exception:
            pass
