"""Reddit client — public JSON endpoints, no OAuth needed for reads.

Reddit asks for a descriptive User-Agent and rate-limits aggressively
(60 req/min by default). We pace requests with `page_delay`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import httpx
import structlog

log = structlog.get_logger()

USER_AGENT = "ScamLens/0.1 (+https://scamlens.vendly.my)"
BASE = "https://www.reddit.com"


@dataclass
class RedditPost:
    id: str
    subreddit: str
    permalink: str
    title: str
    selftext: str
    author: str
    created_utc: float
    url: str   # external URL the post links to (often the actual scam)


class RedditClient:
    def __init__(self, timeout: float = 15):
        self._timeout = timeout

    async def search(
        self,
        query: str,
        subreddits: Optional[list[str]] = None,
        max_pages: int = 5,
        page_delay: float = 1.5,
    ) -> AsyncIterator[RedditPost]:
        """Walks Reddit search. If subreddits given, restricts; otherwise
        searches all of Reddit."""
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            if subreddits:
                for sub in subreddits:
                    async for p in self._iter_search(client, query, sub, max_pages, page_delay):
                        yield p
            else:
                async for p in self._iter_search(client, query, None, max_pages, page_delay):
                    yield p

    async def _iter_search(
        self,
        client: httpx.AsyncClient,
        query: str,
        subreddit: Optional[str],
        max_pages: int,
        page_delay: float,
    ) -> AsyncIterator[RedditPost]:
        path = f"/r/{subreddit}/search.json" if subreddit else "/search.json"
        after: Optional[str] = None
        for page in range(max_pages):
            params = {
                "q": query,
                "sort": "new",
                "limit": 25,
                "restrict_sr": "on" if subreddit else "off",
            }
            if after:
                params["after"] = after
            try:
                resp = await client.get(BASE + path, params=params)
            except Exception as exc:
                log.warning("reddit_fetch_failed", error=str(exc)[:200])
                return
            if resp.status_code == 429:
                log.warning("reddit_rate_limited")
                await asyncio.sleep(30)
                return
            if resp.status_code >= 400:
                log.warning("reddit_error", status=resp.status_code, body=resp.text[:200])
                return

            data = resp.json().get("data") or {}
            children = data.get("children") or []
            for c in children:
                d = c.get("data") or {}
                yield RedditPost(
                    id=d.get("id", ""),
                    subreddit=d.get("subreddit", "") or "",
                    permalink=BASE + (d.get("permalink") or ""),
                    title=d.get("title", "") or "",
                    selftext=d.get("selftext", "") or "",
                    author=d.get("author", "") or "",
                    created_utc=float(d.get("created_utc") or 0),
                    url=d.get("url", "") or "",
                )

            after = data.get("after")
            if not after:
                return
            await asyncio.sleep(page_delay)
