"""/api/events/blocks — SSE stream of block events for the logged-in user.

The user sees blocks for themselves + any accepted wards. The EventBus
distributes events received via Redis pubsub to per-user asyncio queues.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from ..auth import Principal, current_principal
from ..deps import get_event_bus

router = APIRouter(tags=["events"])


@router.get("/events/blocks")
async def sse_blocks(
    request: Request,
    who: Principal = Depends(current_principal),
    bus=Depends(get_event_bus),
):
    """Server-Sent Events stream. Sends block events for the current user
    plus their accepted wards in real time."""

    async def _stream():
        q = bus.subscribe(who.id)
        try:
            while True:
                # Check if client disconnected.
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent proxy/browser timeout.
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(who.id, q)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: don't buffer SSE
        },
    )
