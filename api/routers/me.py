"""/api/me/* — actions a logged-in user can perform on their own account.

Includes:
  - dependents: list, invite by code, accept invitation, revoke
  - blocks: this user's block events (their own + their wards')
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import Principal, current_principal
from ..deps import get_pool

router = APIRouter(prefix="/me", tags=["me"])


# ----------------------------- models ---------------------------------------

class InviteRequest(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=32)


class LinkRow(BaseModel):
    link_id: int
    other_id: int
    other_email: str
    other_invite_code: str
    role_in_link: str            # "guardian" or "ward" — relative to current user
    status: str                  # pending | accepted | rejected | revoked
    invited_at: str
    responded_at: str | None


# ----------------------------- dependents -----------------------------------

@router.get("/dependents")
async def list_links(
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    """Returns every link the user is part of, with their role in each.

    `wards` — accounts the current user watches over (other = ward).
    `guardians` — accounts watching over the current user (other = guardian).
    `pending_outgoing` — invites I sent that haven't been accepted.
    `pending_incoming` — invites I received and need to act on.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              gl.id           AS link_id,
              gl.guardian_id,
              gl.ward_id,
              gl.status,
              gl.invited_at,
              gl.responded_at,
              g.email          AS guardian_email,
              g.invite_code    AS guardian_code,
              w.email          AS ward_email,
              w.invite_code    AS ward_code
            FROM guardian_links gl
            JOIN users g ON g.id = gl.guardian_id
            JOIN users w ON w.id = gl.ward_id
            WHERE gl.guardian_id = $1 OR gl.ward_id = $1
            ORDER BY gl.invited_at DESC
            """,
            who.id,
        )

    wards: list[dict] = []
    guardians: list[dict] = []
    pending_in: list[dict] = []
    pending_out: list[dict] = []
    for r in rows:
        is_guardian = r["guardian_id"] == who.id
        other_id = r["ward_id"] if is_guardian else r["guardian_id"]
        item = {
            "link_id": r["link_id"],
            "other_id": other_id,
            "other_email": r["ward_email"] if is_guardian else r["guardian_email"],
            "other_invite_code": r["ward_code"] if is_guardian else r["guardian_code"],
            "role_in_link": "guardian" if is_guardian else "ward",
            "status": r["status"],
            "invited_at": r["invited_at"].isoformat() + "Z",
            "responded_at": r["responded_at"].isoformat() + "Z" if r["responded_at"] else None,
        }
        if r["status"] == "accepted":
            (wards if is_guardian else guardians).append(item)
        elif r["status"] == "pending":
            (pending_out if is_guardian else pending_in).append(item)

    return {
        "self": {
            "id": who.id,
            "email": who.email,
            "invite_code": who.invite_code,
        },
        "wards": wards,
        "guardians": guardians,
        "pending_outgoing": pending_out,
        "pending_incoming": pending_in,
    }


@router.post("/dependents/invite")
async def invite_dependent(
    body: InviteRequest = Body(...),
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    """Add a dependent (ward) by their invite code. Creates a `pending`
    link; the ward must accept via /api/me/dependents/{link_id}/accept."""
    code = body.invite_code.strip().upper()
    if code == who.invite_code:
        raise HTTPException(400, "you can't add yourself")

    async with pool.acquire() as conn:
        target = await conn.fetchrow(
            "SELECT id, email FROM users WHERE invite_code = $1", code,
        )
        if not target:
            raise HTTPException(404, "no user with that invite code")
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO guardian_links (guardian_id, ward_id, status)
                VALUES ($1, $2, 'pending')
                ON CONFLICT (guardian_id, ward_id) DO UPDATE
                  SET status = 'pending', invited_at = now(), responded_at = NULL
                RETURNING id, status
                """,
                who.id, target["id"],
            )
        except Exception as exc:
            raise HTTPException(400, f"could not create link: {exc}")

    return {
        "link_id": row["id"],
        "status": row["status"],
        "ward_email": target["email"],
    }


@router.post("/dependents/{link_id}/accept")
async def accept_link(
    link_id: int,
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    """Ward accepts an incoming invite."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE guardian_links
            SET status = 'accepted', responded_at = now()
            WHERE id = $1 AND ward_id = $2 AND status = 'pending'
            RETURNING id
            """,
            link_id, who.id,
        )
    if not row:
        raise HTTPException(404, "no pending invite for you with that id")
    return {"link_id": link_id, "status": "accepted"}


@router.post("/dependents/{link_id}/reject")
async def reject_link(
    link_id: int,
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE guardian_links
            SET status = 'rejected', responded_at = now()
            WHERE id = $1 AND ward_id = $2 AND status = 'pending'
            RETURNING id
            """,
            link_id, who.id,
        )
    if not row:
        raise HTTPException(404, "no pending invite for you with that id")
    return {"link_id": link_id, "status": "rejected"}


@router.delete("/dependents/{link_id}")
async def revoke_link(
    link_id: int,
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    """Either side can revoke an active or pending link."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            DELETE FROM guardian_links
            WHERE id = $1 AND (guardian_id = $2 OR ward_id = $2)
            RETURNING id
            """,
            link_id, who.id,
        )
    if not row:
        raise HTTPException(404, "no link with that id involving you")
    return {"link_id": link_id, "removed": True}


# ----------------------------- blocks (placeholder) -------------------------

@router.get("/blocks")
async def my_blocks(
    limit: int = 50,
    who: Principal = Depends(current_principal),
    pool=Depends(get_pool),
):
    """Block events for this user + accepted wards. user_id binding will be
    populated once per-user DoH routing lands; for now returns rows that
    already have user_id set."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, domain, reason, verdict, risk_score, ai_confidence,
                   mimics_brand, host(resolved_ip) AS resolved_ip,
                   user_id, created_at
            FROM blocked_attempts
            WHERE user_id = $1 OR user_id IN (
              SELECT ward_id FROM guardian_links
              WHERE guardian_id = $1 AND status = 'accepted'
            )
            ORDER BY created_at DESC LIMIT $2
            """,
            who.id, min(limit, 200),
        )
    return {
        "items": [
            {**dict(r), "created_at": r["created_at"].isoformat() + "Z"}
            for r in rows
        ],
    }
