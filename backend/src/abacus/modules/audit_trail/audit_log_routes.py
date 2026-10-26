"""ADM-07's live reads (G-02-T08; SPEC-349 §4; `docs/contracts/audit-log.md` v1): the list and
the detail, on the contract's router. The export routes stay the stub's until G-02-T17.

Each route checks the principal first (security review L1: a client principal 404, the agent and
the system 403), then `audit_log.explorer` (404 while off), then narrows every event to what the
reader may see (`explorer.shown_to`)."""

from __future__ import annotations

from datetime import date
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated
from uuid import UUID

from fastapi import Path, Query

from abacus.modules.audit_trail import explorer
from abacus.modules.audit_trail.audit_log_contract import (
    ActorKind,
    AuditEventDetail,
    AuditEventPageOut,
    Ctx,
    authorised,
    gate,
    router,
)

Text = Annotated[str | None, Query(max_length=200)]


@router.get("", action="audit_event.read", response_model=AuditEventPageOut)
async def list_audit_events_route(
    ctx: Ctx,
    actor_kind: Annotated[ActorKind | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
    object_type: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    office_id: Annotated[UUID | None, Query()] = None,
    ip: Annotated[IPv4Address | IPv6Address | None, Query()] = None,
    q: Text = None,
    since_seq: Annotated[int | None, Query(ge=0)] = None,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditEventPageOut:
    """ADM-07 a, b, f: newest first by `seq` (oldest first after `since_seq`). Dates filter on
    `effective_at` in the firm's time zone; `office_id` is the object's office (DEC-415 Q9);
    `q` searches actor, target and fact labels only, never a value (M4); `ip` filters only for
    the readers who see request context (DEC-420)."""
    await authorised(ctx, "audit_event.read")
    await gate(ctx)
    where = explorer.EventFilter(
        actor_kind=actor_kind,
        actor_id=actor_id,
        object_type=object_type,
        action=action,
        from_date=from_,
        to_date=to,
        office_id=office_id,
        ip=str(ip) if ip is not None else None,
        q=q,
        since_seq=since_seq,
    )
    page = await explorer.list_events(ctx, where, cursor, limit)
    return AuditEventPageOut.model_validate(page.model_dump())


@router.get("/{seq}", action="audit_event.read", response_model=AuditEventDetail)
async def audit_event_route(seq: Annotated[int, Path(ge=1)], ctx: Ctx) -> AuditEventDetail:
    """ADM-07 c: one event; a walled or invisible one answers 404 (DEC-43)."""
    await authorised(ctx, "audit_event.read")
    await gate(ctx)
    return await explorer.get_event(ctx, seq)
