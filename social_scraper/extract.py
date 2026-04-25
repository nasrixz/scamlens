"""URL + domain extraction from social-post text."""
from __future__ import annotations

import re
from urllib.parse import urlparse

URL_RE = re.compile(
    r"https?://[^\s<>\"'`)\]]+",
    re.IGNORECASE,
)

# Common URL-shorteners. We let them through (the scanner expands them when
# Playwright navigates), but we also strip surrounding punctuation.
TRAILING_PUNCT = ".,;:!?\"')]}"


def extract_urls(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for m in URL_RE.findall(text):
        url = m
        # Strip trailing punctuation that frequently follows a link in prose.
        while url and url[-1] in TRAILING_PUNCT:
            url = url[:-1]
        if not url:
            continue
        out.append(url)
    # De-dupe preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        deduped.append(u)
    return deduped


def url_to_domain(url: str) -> str:
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        return host
    except Exception:
        return ""
