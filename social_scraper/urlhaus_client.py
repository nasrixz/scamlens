"""URLhaus feed importer — abuse.ch curated malicious URL list.

URLhaus is a public, free anti-malware feed maintained by abuse.ch. URLs
listed there have already been classified as malicious (malware drop,
phishing, etc.) so we DON'T need to re-scan with AI — direct promote
into blocklist with the URLhaus reference URL as the source link.

Free CSV endpoint: https://urlhaus.abuse.ch/downloads/csv_recent/
   format: # comment lines, then `id,dateadded,url,url_status,last_online,threat,tags,urlhaus_link,reporter`
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
import structlog

log = structlog.get_logger()

URLHAUS_RECENT = "https://urlhaus.abuse.ch/downloads/csv_recent/"


@dataclass
class URLhausEntry:
    id: str
    date_added: str
    url: str
    status: str        # online | offline | unknown
    threat: str        # malware_download | phishing | ...
    tags: str
    reference: str     # urlhaus.abuse.ch reference page
    reporter: str


class URLhausClient:
    def __init__(self, timeout: float = 30):
        self._timeout = timeout

    async def recent(self) -> AsyncIterator[URLhausEntry]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                resp = await c.get(URLHAUS_RECENT)
            resp.raise_for_status()
        except Exception as exc:
            log.warning("urlhaus_fetch_failed", error=str(exc)[:200])
            return

        text = resp.text
        # Skip leading comment lines (start with '#').
        body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
        reader = csv.reader(io.StringIO(body))
        for row in reader:
            if len(row) < 9:
                continue
            try:
                yield URLhausEntry(
                    id=row[0].strip('"'),
                    date_added=row[1].strip('"'),
                    url=row[2].strip('"'),
                    status=row[3].strip('"'),
                    threat=row[5].strip('"'),
                    tags=row[6].strip('"'),
                    reference=row[7].strip('"'),
                    reporter=row[8].strip('"'),
                )
            except IndexError:
                continue
