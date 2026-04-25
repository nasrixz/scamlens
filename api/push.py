"""Web Push send + subscription persistence.

Uses pywebpush to send to browser endpoints. VAPID keys come from env;
generate once via scripts.gen_vapid and store in .env.

Stale subscription endpoints (HTTP 404 / 410) are deleted automatically
so the user doesn't keep accumulating dead push channels.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import structlog

log = structlog.get_logger()


class PushSender:
    def __init__(self, public_key: str, private_key: str, contact: str):
        self._public_key = public_key
        self._private_key = private_key
        self._contact = contact
        # Lazy-import so the API still boots when keys aren't configured yet.
        try:
            from pywebpush import webpush, WebPushException  # noqa: F401
            self._available = bool(public_key and private_key)
        except Exception:
            self._available = False

    @property
    def public_key(self) -> str:
        return self._public_key

    @property
    def available(self) -> bool:
        return self._available

    async def send_to_user(
        self,
        pool,
        user_id: int,
        title: str,
        body: str,
        url: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> int:
        """Send a push to every subscription belonging to user_id. Returns
        the number of successful sends. Dead endpoints are pruned."""
        if not self._available:
            log.info("push_skipped", reason="vapid_not_configured")
            return 0

        async with pool.acquire() as conn:
            subs = await conn.fetch(
                "SELECT id, endpoint, p256dh, auth FROM push_subscriptions "
                "WHERE user_id = $1",
                user_id,
            )
        if not subs:
            return 0

        sent = 0
        dead_ids: list[int] = []
        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url or "/",
            "tag": tag or "scamlens",
        })

        # pywebpush is sync; offload to a thread per subscription.
        for sub in subs:
            ok, dead = await asyncio.to_thread(
                self._send_one, sub["endpoint"], sub["p256dh"], sub["auth"], payload,
            )
            if ok:
                sent += 1
            elif dead:
                dead_ids.append(sub["id"])

        if dead_ids:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM push_subscriptions WHERE id = ANY($1::bigint[])",
                    dead_ids,
                )
            log.info("push_pruned_dead", count=len(dead_ids))
        return sent

    def _send_one(
        self, endpoint: str, p256dh: str, auth: str, payload: str,
    ) -> tuple[bool, bool]:
        from pywebpush import webpush, WebPushException

        sub = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=self._private_key,
                vapid_claims={"sub": self._contact},
                ttl=3600,
            )
            return True, False
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", 0) if exc.response else 0
            dead = status in (404, 410)
            log.info("push_failed", status=status, dead=dead, error=str(exc)[:160])
            return False, dead
        except Exception as exc:
            log.warning("push_error", error=str(exc)[:160])
            return False, False
