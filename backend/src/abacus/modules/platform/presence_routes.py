"""Presence routes (F-08-T13; TASK-8845; `docs/contracts/presence.md`; DEC-5844)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.platform import presence as svc

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class PresenceIn(BaseModel):
    model_config = _cfg()

    object_kind: Annotated[str, Field(pattern=r"^[a-z][a-z_]{0,39}$"), Internal]
    object_id: Annotated[UUID, Internal]
    anchor_kind: Annotated[svc.AnchorKind, Internal]
    anchor_key: Annotated[str | None, Field(min_length=1, max_length=120), Internal] = None


class PresenceOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    anchor_kind: Annotated[svc.AnchorKind, Internal]
    anchor_key: Annotated[str | None, Internal] = None
    seen_at: Annotated[datetime, Internal]


class PresenceListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[PresenceOut], Internal]
    heartbeat_seconds: Annotated[int, Internal] = svc.HEARTBEAT_SECONDS
    ttl_seconds: Annotated[int, Internal] = int(svc.TTL.total_seconds())


presence_router = AbacusRouter(prefix="/v1", tags=["presence"])


class PresenceAckOut(BaseModel):
    model_config = _cfg()

    heartbeat_seconds: Annotated[int, Internal] = svc.HEARTBEAT_SECONDS
    ttl_seconds: Annotated[int, Internal] = int(svc.TTL.total_seconds())


@presence_router.put("/presence", action="presence.update", response_model=PresenceAckOut)
async def presence_heartbeat_route(body: PresenceIn, ctx: Ctx) -> PresenceAckOut:
    """A heartbeat every 15 s; gone after 45 s. An unregistered kind or an object the caller cannot
    read answers 404 (fail closed, INV-3)."""
    await svc.heartbeat(ctx, body.object_kind, body.object_id, body.anchor_kind, body.anchor_key)
    return PresenceAckOut()


@presence_router.get("/presence", action="presence.read", response_model=PresenceListOut)
async def presence_route(object_kind: str, object_id: UUID, ctx: Ctx) -> PresenceListOut:
    found = await svc.present(ctx, object_kind, object_id)
    return PresenceListOut(
        items=[
            PresenceOut(
                user_id=p.user_id,
                anchor_kind=p.anchor_kind,
                anchor_key=p.anchor_key,
                seen_at=p.seen_at,
            )
            for p in found
        ]
    )


__all__ = ["presence_router"]
