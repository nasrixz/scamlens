"""Runtime config for the social scraper."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    redis_url: str
    scanner_url: str

    threads_token: str
    threads_user_id: str        # optional — only needed if Threads requires it
    threads_search_type: str    # RECENT | TOP

    keywords: list[str]

    duration_minutes: int       # how long each scrape window runs
    interval_hours: int         # how often to start a new window
    max_pages_per_keyword: int
    request_delay_seconds: float
    confidence_threshold: int   # min AI confidence to add to blocklist

    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        kws = os.getenv("THREADS_KEYWORDS", DEFAULT_KEYWORDS)
        return cls(
            database_url=_pg(os.getenv("DATABASE_URL", "")),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            scanner_url=os.getenv("SCANNER_URL", "http://ai_scanner:8090"),
            threads_token=os.getenv("THREADS_ACCESS_TOKEN", ""),
            threads_user_id=os.getenv("THREADS_USER_ID", "me"),
            threads_search_type=os.getenv("THREADS_SEARCH_TYPE", "RECENT").upper(),
            keywords=[k.strip() for k in kws.split(",") if k.strip()],
            duration_minutes=int(os.getenv("SCRAPE_DURATION_MINUTES", "60")),
            interval_hours=int(os.getenv("SCRAPE_INTERVAL_HOURS", "24")),
            max_pages_per_keyword=int(os.getenv("SCRAPER_MAX_PAGES", "10")),
            request_delay_seconds=float(os.getenv("SCRAPER_REQUEST_DELAY", "2.0")),
            confidence_threshold=int(os.getenv("SCRAPER_CONFIDENCE", "70")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


def _pg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


DEFAULT_KEYWORDS = (
    # English
    "scam,fraud,phishing,fake,fake bank,fake login,phishing site,"
    "free crypto,double bitcoin,investment scam,"
    "lottery winner,prize claim,government refund,"
    # Malay (since the deployment is .my)
    "penipuan,penipuan online,laman palsu,scam loan,"
    "pinjaman peribadi cepat lulus,"
    "tipu,tipu duit,akaun bank tergantung,"
    # Money / brand bait
    "free duit raya,kerja online dapat duit,"
    "paypal locked,maybank verify,cimb verify"
)
