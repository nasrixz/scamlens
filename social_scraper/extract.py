"""URL + domain extraction from social-post text.

Threads posts contain emojis, zero-width chars, and replacement characters
right next to URLs (e.g. paste an unicode \\ufffd onto a URL's tail). We
match permissively and then strip a wide trailing-junk character class so
the resulting URL is something Playwright can actually navigate.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Match `https://...` until any whitespace. Unicode-aware. Subsequent
# clean-up trims junk that latches onto the end.
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

# Strip these from the trailing edge after capture: punctuation, brackets,
# emoji presentation selectors, replacement char, and combining marks.
_TRAILING_JUNK = set(".,;:!?\"')]}>" " �​‌‍️⁠")


def _trim_trailing_junk(url: str) -> str:
    while url and (url[-1] in _TRAILING_JUNK or _is_emoji(url[-1])):
        url = url[:-1]
    return url


def _is_emoji(ch: str) -> bool:
    """Cheap emoji-block check covering most pictographic ranges."""
    cp = ord(ch)
    return (
        0x1F300 <= cp <= 0x1FAFF   # symbols, supplementary, recent emoji
        or 0x2600 <= cp <= 0x27BF  # misc symbols, dingbats
        or 0x1F1E6 <= cp <= 0x1F1FF  # regional indicator (flags)
    )


def extract_urls(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for m in URL_RE.findall(text):
        url = _trim_trailing_junk(m)
        if not url or len(url) < 11:    # 'http://a.bc' minimum
            continue
        # Discard if no host.
        try:
            host = urlparse(url).hostname
        except Exception:
            continue
        if not host or "." not in host:
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
