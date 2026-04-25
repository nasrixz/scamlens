"""Block-event broadcaster.

A single Redis pubsub subscriber listens to `scamlens:block_events`. For
each event it:
  1. Fans out a Web Push to the user themselves AND every guardian.
  2. Broadcasts to per-user asyncio queues so SSE clients can stream.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, AsyncIterator

import structlog

log = structlog.get_logger()

CHANNEL = "scamlens:block_events"


class EventBus:
    def __init__(self):
        self._listeners: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, user_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._listeners[user_id].add(q)
        return q

    def unsubscribe(self, user_id: int, q: asyncio.Queue) -> None:
        self._listeners.get(user_id, set()).discard(q)
        if not self._listeners.get(user_id):
            self._listeners.pop(user_id, None)

    def fanout(self, user_ids: list[int], event: dict[str, Any]) -> None:
        for uid in user_ids:
            for q in list(self._listeners.get(uid, ())):
                if q.full():
                    try:
                        q.get_nowait()  # drop oldest
                    except Exception:
                        pass
                try:
                    q.put_nowait(event)
                except Exception:
                    pass


async def run_subscriber(redis, pool, push_sender, bus: EventBus) -> None:
    """Long-running task. Reconnects on transport errors with backoff."""
    backoff = 2
    while True:
        try:
            pubsub = redis.pubsub()
            await pubsub.subscribe(CHANNEL)
            log.info("event_subscriber_ready")
            backoff = 2
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    raw = message.get("data") or "{}"
                    event = json.loads(raw)
                except Exception:
                    continue
                user_id = event.get("user_id")
                if not isinstance(user_id, int):
                    continue
                await _handle_event(pool, push_sender, bus, user_id, event)
        except Exception as exc:
            log.warning("event_subscriber_restart", error=str(exc)[:160])
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def _handle_event(
    pool, push_sender, bus: EventBus, user_id: int, event: dict[str, Any],
) -> None:
    """Fan out: push to user + their guardians, SSE to user + guardians."""
    targets = [user_id]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT guardian_id FROM guardian_links "
            "WHERE ward_id=$1 AND status='accepted'",
            user_id,
        )
        targets.extend(int(r["guardian_id"]) for r in rows)

        ward_email_row = await conn.fetchrow(
            "SELECT email FROM users WHERE id=$1", user_id,
        )
    ward_email = ward_email_row["email"] if ward_email_row else f"user#{user_id}"

    bus.fanout(targets, event)

    # Web push: skip the user themselves only when verdict is mild — for
    # scam verdicts notify everyone in the chain.
    domain = event.get("domain", "?")
    title = "ScamLens blocked a scam"
    body = f"{ward_email} tried to open {domain}"
    for uid in targets:
        try:
            await push_sender.send_to_user(
                pool, uid,
                title=title,
                body=body,
                url="/account",
                tag=f"block-{event.get('verdict') or 'scam'}",
            )
        except Exception as exc:
            log.warning("push_to_user_failed", uid=uid, error=str(exc)[:120])
