"""Pydantic response + request models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StatsResponse(BaseModel):
    total_blocked: int
    blocked_today: int
    unique_domains: int
    top_domains: list["TopDomain"]
    daily: list["DailyCount"]


class TopDomain(BaseModel):
    domain: str
    count: int


class DailyCount(BaseModel):
    day: str  # YYYY-MM-DD
    count: int


class BlockedRow(BaseModel):
    id: int
    domain: str
    reason: str
    verdict: Optional[str] = None
    ai_confidence: Optional[int] = None
    risk_score: Optional[int] = None
    mimics_brand: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime


class BlockedPage(BaseModel):
    items: list[BlockedRow]
    total: int
    page: int
    page_size: int


class ReportRequest(BaseModel):
    domain: str = Field(..., min_length=3, max_length=253)
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("domain")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().lower()
        # Strip scheme + path if user pasted a URL.
        for prefix in ("https://", "http://"):
            if v.startswith(prefix):
                v = v[len(prefix):]
        v = v.split("/")[0].split("?")[0].rstrip(".")
        if not v or " " in v or "." not in v:
            raise ValueError("invalid domain")
        return v


class ReportResponse(BaseModel):
    id: int
    domain: str
    status: str


class CheckResponse(BaseModel):
    domain: str
    verdict: str  # safe | suspicious | scam | pending | unknown
    risk_score: Optional[int] = None
    confidence: Optional[int] = None
    reason: Optional[str] = None
    mimics_brand: Optional[str] = None
    source: str
    cached: bool


class SetupResponse(BaseModel):
    platform: str
    dns_hostname: str
    block_page_ip: str
    steps: list[str]
    notes: list[str] = []
