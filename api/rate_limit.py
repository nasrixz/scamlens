"""SlowAPI rate limiter — keyed on client IP. Shared singleton so routers can
import the same decorator."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address


def _key(request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_key, default_limits=[])
