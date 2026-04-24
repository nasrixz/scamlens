"""Playwright-based page fetcher.

Visits a domain in a locked-down Chromium context and returns HTML + PNG
screenshot. Scam sites are hostile, so we:
- force headless, disable downloads
- short timeout (no infinite-redirect loops)
- cap HTML + screenshot size before hitting the AI
- try https first, http fallback
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PWTimeoutError,
    async_playwright,
)

log = structlog.get_logger()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class PageCapture:
    url: str
    final_url: str
    status: int
    html: str
    screenshot_png: bytes
    title: str


class PageFetcher:
    def __init__(self, scan_timeout: int, max_html_chars: int, screenshot_max_bytes: int):
        self._timeout_ms = scan_timeout * 1000
        self._max_html = max_html_chars
        self._max_screenshot = screenshot_max_bytes
        self._pw = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
            ],
        )
        log.info("fetcher_ready")

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def fetch(self, domain: str) -> Optional[PageCapture]:
        assert self._browser is not None
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            capture = await self._try_one(url)
            if capture is not None:
                return capture
        return None

    async def _try_one(self, url: str) -> Optional[PageCapture]:
        assert self._browser is not None
        context: BrowserContext = await self._browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US",
        )
        # Drop heavy + risky asset types.
        async def _router(route):
            if route.request.resource_type in ("media", "font"):
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", _router)

        page: Page = await context.new_page()
        try:
            response = await asyncio.wait_for(
                page.goto(url, wait_until="load"),
                timeout=self._timeout_ms / 1000,
            )
            status = response.status if response else 0
            # Give scripts a moment to render.
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except PWTimeoutError:
                pass

            html = (await page.content())[: self._max_html]
            title = (await page.title())[:256]
            screenshot = await page.screenshot(full_page=False, type="png")
            if len(screenshot) > self._max_screenshot:
                screenshot = await page.screenshot(
                    full_page=False, type="jpeg", quality=60,
                )
            return PageCapture(
                url=url,
                final_url=page.url,
                status=status,
                html=html,
                screenshot_png=screenshot,
                title=title,
            )
        except (asyncio.TimeoutError, PWTimeoutError):
            log.warning("fetch_timeout", url=url)
            return None
        except Exception as exc:
            log.warning("fetch_error", url=url, error=str(exc)[:200])
            return None
        finally:
            await context.close()
