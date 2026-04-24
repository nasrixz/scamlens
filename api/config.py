"""API runtime config."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    redis_url: str
    scan_queue_key: str
    domain: str
    dns_hostname: str
    block_page_ip: str
    profile_org: str
    profile_identifier: str
    cors_origins: list[str]
    unknown_ttl: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        domain = os.getenv("DOMAIN", "scamlens.example.com")
        dns_hostname = os.getenv("DNS_HOSTNAME", f"dns.{domain}")
        origins = os.getenv("CORS_ORIGINS", f"https://{domain}")
        return cls(
            database_url=_pg(os.getenv("DATABASE_URL", "")),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            scan_queue_key=os.getenv("SCAN_QUEUE_KEY", "scamlens:scan_queue"),
            domain=domain,
            dns_hostname=dns_hostname,
            block_page_ip=os.getenv("BLOCK_PAGE_IP", "0.0.0.0"),
            profile_org=os.getenv("PROFILE_ORG", "ScamLens"),
            profile_identifier=os.getenv("PROFILE_IDENTIFIER", "com.scamlens.dns"),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
            unknown_ttl=int(os.getenv("UNKNOWN_TTL_SECONDS", "300")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


def _pg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)
