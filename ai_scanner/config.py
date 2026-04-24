"""Runtime config for scanner."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    redis_url: str
    database_url: str
    scan_queue_key: str
    safe_ttl: int
    scam_ttl: int
    unknown_ttl: int
    scan_timeout: int
    concurrency: int

    ai_provider: str
    anthropic_api_key: str
    anthropic_model: str
    gemini_api_key: str
    gemini_model: str

    max_html_chars: int
    screenshot_max_bytes: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            database_url=_pg(os.getenv("DATABASE_URL", "")),
            scan_queue_key=os.getenv("SCAN_QUEUE_KEY", "scamlens:scan_queue"),
            safe_ttl=int(os.getenv("SAFE_TTL_SECONDS", "86400")),
            scam_ttl=int(os.getenv("SCAM_TTL_SECONDS", "604800")),
            unknown_ttl=int(os.getenv("UNKNOWN_TTL_SECONDS", "300")),
            scan_timeout=int(os.getenv("SCAN_TIMEOUT_SECONDS", "20")),
            concurrency=int(os.getenv("SCAN_CONCURRENCY", "2")),
            ai_provider=os.getenv("AI_PROVIDER", "anthropic").lower(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            max_html_chars=int(os.getenv("MAX_HTML_CHARS", "120000")),
            screenshot_max_bytes=int(os.getenv("SCREENSHOT_MAX_BYTES", "900000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


def _pg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)
