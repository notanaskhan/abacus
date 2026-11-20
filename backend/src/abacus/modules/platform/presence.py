"""Presence (F-08-T13; TASK-8845; F-08 §F1; C-28; ADR P-15; INV-3; DEC-5844). Amber.

`PUT /v1/presence {object_kind, object_id, anchor_kind, anchor_key}` is a heartbeat every 15
seconds; a heartbeat older than 45 seconds is gone. The object kind must be registered by its owner
(`register_presence_kind(kind, may_read)`: fail closed, the ADR-106 slot pattern) and the caller
must be able to read the object (the owner's check). Each heartbeat replaces the person's row for
that object (`presence_heartbeats`, written through `kernel.ephemeral`: not audited, never through
the outbox) and wakes `presence:<kind>:<id>` with identifiers only; a reader subscribes to that
topic only with the object's read access. Presence never locks anything: it says who is
where.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import realtime
from abacus.kernel.db import tenant_session
from abacus.kernel.ephemeral import ephemeral_write
from abacus.kernel.errors import NotFound

TTL: Final = timedelta(seconds=45)
HEARTBEAT_SECONDS: Final = 15
AnchorKind = Literal["cell", "section", "card", "record"]
MayRead = Callable[[object, UUID], Awaitable[bool]]
_KINDS: dict[str, MayRead] = {}


def register_presence_kind(kind: str, may_read: MayRead) -> None:
    """An object kind's owner: who may read it decides who may be seen on it (INV-3)."""
    known = _KINDS.get(kind)
    if known is not None and known is not may_read:
        raise ValueError(f"presence kind {kind!r} is already registered")
    _KINDS[kind] = may_read


def presence_kinds() -> frozenset[str]:
    return frozenset(_KINDS)


async def _may_read(ctx: object, kind: str, object_id: UUID) -> bool:
    check = _KINDS.get(kind)
    if check is None:
        return False
    try:
        return await check(ctx, object_id)
    except Exception:  # an owner that cannot answer refuses
        return False


def topic(kind: str, object_id: UUID) -> str:
    return f"presence:{kind}:{object_id}"


_UPSERT: Final = (
    "INSERT INTO presence_heartbeats (tenant_id, user_id, object_kind, object_id, anchor_kind, "
    "anchor_key, seen_at) VALUES (:t, :u, :k, :o, :ak, :key, clock_timestamp()) "
    "ON CONFLICT (tenant_id, user_id, object_kind, object_id) DO UPDATE SET "
    "anchor_kind = EXCLUDED.anchor_kind, anchor_key = EXCLUDED.anchor_key, "
    "seen_at = EXCLUDED.seen_at"
)


async def heartbeat(
    ctx: object, kind: str, object_id: UUID, anchor_kind: AnchorKind, anchor_key: str | None
) -> None:
    from abacus.modules.identity.api import AuthContext

    if not isinstance(ctx, AuthContext) or ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise NotFound("presence")  # only people are present
    if not await _may_read(ctx, kind, object_id):
        raise NotFound(kind)  # absent, never forbidden (INV-3)
    await ephemeral_write(
        ctx.tenant,
        _UPSERT,
        {
            "t": ctx.tenant_id,
            "u": ctx.user_id,
            "k": kind,
            "o": object_id,
            "ak": anchor_kind,
            "key": None if anchor_kind == "record" else anchor_key,
        },
    )
    realtime.wake(topic(kind, object_id))


@dataclass(frozen=True)
class Present:
    user_id: UUID
    anchor_kind: AnchorKind
    anchor_key: str | None
    seen_at: datetime


async def present(ctx: object, kind: str, object_id: UUID) -> list[Present]:
    """Who else is on the object now (the viewer never sees themself), oldest join first."""
    from abacus.modules.identity.api import AuthContext

    if not isinstance(ctx, AuthContext) or not await _may_read(ctx, kind, object_id):
        raise NotFound(kind)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT user_id, anchor_kind, anchor_key, seen_at FROM presence_heartbeats "
                    "WHERE object_kind = :k AND object_id = :o AND user_id <> :me "
                    "AND seen_at > clock_timestamp() - make_interval(secs => :ttl) "
                    "ORDER BY seen_at"
                ),
                {"k": kind, "o": object_id, "me": ctx.user_id, "ttl": TTL.total_seconds()},
            )
        ).all()
    return [Present(r.user_id, r.anchor_kind, r.anchor_key, r.seen_at) for r in rows]


async def _presence_topic(ctx: object, ident: str) -> realtime.TopicAccess | None:
    kind, _, raw = ident.partition(":")
    try:
        object_id = UUID(raw)
    except ValueError:
        return None
    return "content" if await _may_read(ctx, kind, object_id) else None


def register() -> None:
    realtime.register_topic("presence", _presence_topic)


__all__ = [
    "HEARTBEAT_SECONDS",
    "TTL",
    "Present",
    "heartbeat",
    "presence_kinds",
    "present",
    "register",
    "register_presence_kind",
    "topic",
]
