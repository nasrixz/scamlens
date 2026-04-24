"""Runtime config loaded from env."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bind_host: str
    dns_port: int
    doh_port: int
    upstream_dns: str
    upstream_dns_fallback: str
    block_ip: str
    block_ttl: int
    redis_url: str
    database_url: str
    safe_ttl: int
    scam_ttl: int
    unknown_ttl: int
    scan_queue_key: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bind_host=os.getenv("DNS_BIND_HOST", "0.0.0.0"),
            dns_port=int(os.getenv("DNS_PORT", "53")),
            doh_port=int(os.getenv("DOH_LISTEN_PORT", "8053")),
            upstream_dns=os.getenv("UPSTREAM_DNS", "1.1.1.1"),
            upstream_dns_fallback=os.getenv("UPSTREAM_DNS_FALLBACK", "1.0.0.1"),
            block_ip=os.getenv("BLOCK_PAGE_IP", "0.0.0.0"),
            block_ttl=int(os.getenv("BLOCK_TTL_SECONDS", "60")),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            database_url=_asyncpg_dsn(os.getenv("DATABASE_URL", "")),
            safe_ttl=int(os.getenv("SAFE_TTL_SECONDS", "86400")),
            scam_ttl=int(os.getenv("SCAM_TTL_SECONDS", "604800")),
            unknown_ttl=int(os.getenv("UNKNOWN_TTL_SECONDS", "300")),
            scan_queue_key=os.getenv("SCAN_QUEUE_KEY", "scamlens:scan_queue"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


def _asyncpg_dsn(url: str) -> str:
    """asyncpg.connect wants plain 'postgresql://', not SQLAlchemy's
    'postgresql+asyncpg://' form. Strip the driver prefix if present."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)
