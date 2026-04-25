"""Thin wrapper over the Threads keyword-search API.

Docs: https://developers.facebook.com/docs/threads/keyword-search

Requirements:
  * Long-lived user access token with scopes
    `threads_basic` + `threads_keyword_search`.
  * The keyword-search endpoint is gated; the token must be issued for an
    app that has been approved for it.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()

GRAPH_BASE = "https://graph.threads.net/v1.0"
DEFAULT_FIELDS = (
    "id,text,media_type,permalink,timestamp,username,"
    "has_replies,is_quote_post,is_reply"
)


@dataclass
class ThreadsPost:
    id: str
    text: str
    media_type: str
    permalink: str
    username: str
    timestamp: str
    has_replies: bool
    is_quote_post: bool
    is_reply: bool


class ThreadsClient:
    def __init__(self, token: str, search_type: str = "RECENT", timeout: float = 15):
        self._token = token
        self._search_type = search_type
        self._timeout = timeout

    async def keyword_search(
        self,
        query: str,
        max_pages: int = 10,
        page_delay: float = 1.5,
    ) -> AsyncIterator[ThreadsPost]:
        """Yield posts matching `query`. Walks the cursor up to `max_pages`."""
        after: Optional[str] = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for page in range(max_pages):
                params = {
                    "q": query,
                    "search_type": self._search_type,
                    "fields": DEFAULT_FIELDS,
                    "limit": 25,
                    "access_token": self._token,
                }
                if after:
                    params["after"] = after

                payload = await self._get(client, "/keyword_search", params)
                if not payload:
                    return
                for raw in payload.get("data", []):
                    yield ThreadsPost(
                        id=raw.get("id", ""),
                        text=raw.get("text", "") or "",
                        media_type=(raw.get("media_type") or "").upper(),
                        permalink=raw.get("permalink", "") or "",
                        username=raw.get("username", "") or "",
                        timestamp=raw.get("timestamp", "") or "",
                        has_replies=bool(raw.get("has_replies")),
                        is_quote_post=bool(raw.get("is_quote_post")),
                        is_reply=bool(raw.get("is_reply")),
                    )

                paging = payload.get("paging") or {}
                cursors = paging.get("cursors") or {}
                next_after = cursors.get("after")
                if not next_after:
                    return
                after = next_after
                await asyncio.sleep(page_delay)

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> Optional[dict]:
        url = GRAPH_BASE + path
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type(httpx.TransportError),
                reraise=True,
            ):
                with attempt:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 429:
                        log.warning("threads_rate_limited")
                        await asyncio.sleep(30)
                        return None
                    if resp.status_code >= 400:
                        log.warning(
                            "threads_error",
                            status=resp.status_code,
                            body=resp.text[:300],
                        )
                        return None
                    return resp.json()
        except Exception as exc:
            log.warning("threads_fetch_failed", error=str(exc)[:200])
            return None
