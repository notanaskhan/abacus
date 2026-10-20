"""The audit log explorer (SPEC-304; TASK-305): the firm's trail, read by firm admins and the
practice leader, newest first, filtered and paged. Events carry identifiers only (ADR-007); names
are resolved for people."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.uow import AuditFilter, AuditRow, audit_facets, audit_page
from abacus.modules.identity.api import AuthContext, Resource, authorise, names_of

PAGE: Final = 100


@dataclass(frozen=True)
class EventView:
    seq: int
    occurred_at: datetime
    actor_kind: str
    actor_id: str
    actor_name: str | None
    action: str
    target_type: str
    target_id: str
    before_ref: dict[str, str | int] | None
    after_ref: dict[str, str | int] | None
    trace_id: str | None


@dataclass(frozen=True)
class EventPage:
    events: list[EventView]
    next_before: int | None


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def events(
    ctx: AuthContext, where: AuditFilter, before_seq: int | None, limit: int = PAGE
) -> EventPage:
    """AC-1, AC-2."""
    await authorise(ctx, "audit.read", Resource.firm(ctx.tenant_id))
    size = max(1, min(limit, PAGE))
    async with tenant_session(ctx.tenant) as session:
        rows: list[AuditRow] = await audit_page(session, where, before_seq, size + 1)
    more = len(rows) > size
    rows = rows[:size]
    people: list[UUID] = sorted(
        {u for r in rows if r.actor_kind == "human" and (u := _uuid(r.actor_id)) is not None},
        key=str,
    )
    names = await names_of(people)
    return EventPage(
        [
            EventView(
                r.seq,
                r.occurred_at,
                r.actor_kind,
                r.actor_id,
                names.get(u) if (u := _uuid(r.actor_id)) is not None else None,
                r.action,
                r.target_type,
                r.target_id,
                r.before_ref,
                r.after_ref,
                r.trace_id,
            )
            for r in rows
        ],
        rows[-1].seq if more and rows else None,
    )


async def facets(ctx: AuthContext) -> tuple[list[str], list[str]]:
    """AC-3: the actions and target types to filter by."""
    await authorise(ctx, "audit.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        return await audit_facets(session)
