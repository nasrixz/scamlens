"""/api/push/* + /api/me/push/* — Web Push subscription management."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import Principal, current_principal
from ..deps import get_cfg, get_pool, get_push

router = APIRouter()


class SubscribeRequest(BaseModel):
    endpoint: str = Field(..., max_length=2048)
    p256dh: str = Field(..., max_length=512)
    auth: str = Field(..., max_length=512)
    user_agent: str | None = Field(None, max_length=512)


@router.get("/push/key")
async def push_public_key(cfg=Depends(get_cfg)):
    """Public VAPID key — frontend uses this to register a PushSubscription."""
    if not cfg.vapid_public_key:
        raise HTTPException(503, "push not configured")
    return {"public_key": cfg.vapid_public_key}


@router.post("/me/push/subscribe")
async def subscribe(
    body: SubscribeRequest = Body(...),
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    """Persist a browser PushSubscription. Idempotent on (user_id, endpoint)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO push_subscriptions
              (user_id, endpoint, p256dh, auth, user_agent, last_seen_at)
            VALUES ($1, $2, $3, $4, $5, now())
            ON CONFLICT (user_id, endpoint) DO UPDATE SET
              p256dh = EXCLUDED.p256dh,
              auth   = EXCLUDED.auth,
              user_agent = EXCLUDED.user_agent,
              last_seen_at = now()
            """,
            who.id, body.endpoint, body.p256dh, body.auth, body.user_agent,
        )
    return {"ok": True}


@router.delete("/me/push/subscribe")
async def unsubscribe(
    body: SubscribeRequest = Body(...),
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM push_subscriptions WHERE user_id=$1 AND endpoint=$2",
            who.id, body.endpoint,
        )
    return {"ok": True}


@router.post("/me/push/test")
async def test_push(
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
    push_sender=Depends(get_push),
):
    """Send a test notification to all the user's subscriptions."""
    sent = await push_sender.send_to_user(
        pool, who.id,
        title="ScamLens",
        body="Notifications are working ✓",
        url="/account",
        tag="test",
    )
    return {"sent": sent}
