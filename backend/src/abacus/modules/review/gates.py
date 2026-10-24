"""The human-gate projection: what waits on a person (P-04-T16; P-04 §3 F9, §4.4; C13; DF-25,
DEC-28, DEC-320). PROTECTED.

`human_gates` is a rebuildable projection that Home reads (I-01): one row per gate subject, `open`
while a person still has to act, `done` once nobody does. It is never the record of anything.

- **Sources** (`register_gate_source`): each owner names its gate kind (the DF-25 taxonomy), the
  subject type, the read action a person needs on the engagement to see its gates (`visible()`,
  so a wall hides them), the outbox events that may change it, and `open_for(tenant,
  engagement_id | None)`: the subjects waiting on a person now (the owner computes this from its
  own records; `None` means every engagement, for the rebuild).
- **The projector** (`apply_event`, `review.api.SUBSCRIPTIONS`): for an event, each source it may
  change reconciles the engagement's rows with `open_for`, inside one system unit of work holding
  a transaction lock on (tenant, source, engagement), so two events about one engagement never
  interleave their reads and writes. A new subject is inserted `open`, with a `source_event_id`
  derived from the event and the subject, so a redelivered event inserts nothing (the table's
  `human_gates_once`) and a second event about the same subject does nothing either
  (`human_gates_one_per_subject`, 0152); a subject no longer waiting goes `done`, one waiting
  again goes `open`. Nothing changed, nothing is written: replaying the same events leaves the
  table, and the audit trail, unchanged. The reconcile reads the owner's state, never the event's
  payload, so events may arrive in any order (the relay promises no order).
- **Rebuild** (`rebuild_human_gates`): every source, every engagement; the same rows as the
  events produced.
- **Read** (`gates_waiting_on`): open rows assigned to the caller or unassigned, through
  `visible(human_gate.read)` and the source's own read action; `counts` per kind.

`register_gate_kind` (P-04-T06, `slots`) is a different slot: a computed gate's check (G1 to G5).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, and_, false, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.listing import (
    ListPage,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
    status_counts,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.review.models import HumanGate

_log = get_logger(__name__)

# DF-25: the one taxonomy (human_gates.kind CHECK, 0093).
GATE_KINDS: Final = frozenset(
    {"decision", "sign_off_request", "proposal", "send", "final_approval", "export", "release"}
)
# The outbox events the projector subscribes to (C13). A source may only name these: the worker's
# subscriptions are fixed at import, before every owner has registered.
C13_EVENTS: Final = frozenset(
    {
        "proposal.recorded",  # agents: a screening, upload review, match or guidance draft
        "guidance_draft.decided",  # agents: a person approved or discarded a draft
        "review_decision.recorded",  # evidence: a decision on a version, or its undo
        "inbox_file.sorted",  # evidence: an inbox file assigned or discarded
        "evidence_version.withdrawn",  # evidence: nothing derived from it waits on anyone
    }
)
READ: Final = "human_gate.read"
RESOURCE: Final = "human_gates"
_CODE: Final = re.compile(r"[a-z][a-z_]{0,39}")
_NAMESPACE: Final = uuid.UUID("6f1b7a52-3c8e-4f0b-9a57-2f6c1d0e8b13")


@dataclass(frozen=True)
class OpenGate:
    """A subject waiting on a person, as its owner says now."""

    subject_id: UUID
    engagement_id: UUID
    assignee_user_id: UUID | None = None
    role: str | None = None
    due_on: date | None = None
    work_item_id: UUID | None = None
    client_id: UUID | None = None


OpenFor = Callable[[TenantContext, UUID | None], Awaitable[Sequence[OpenGate]]]


@dataclass(frozen=True)
class GateSource:
    subject_type: str
    kind: str
    read_action: str
    events: frozenset[str]
    open_for: OpenFor


_SOURCES: dict[str, GateSource] = {}


def register_gate_source(source: GateSource) -> None:
    """Register an owner's gates (once, at the owner's import)."""
    if not _CODE.fullmatch(source.subject_type):
        raise ValueError(f"gate subject {source.subject_type!r} must be snake_case")
    if source.kind not in GATE_KINDS:
        raise ValueError(f"{source.kind!r} is not a DF-25 gate kind")
    unknown = sorted(source.events - C13_EVENTS)
    if unknown or not source.events:
        raise ValueError(f"gate events must be C13's subscribed events: {', '.join(unknown)}")
    known = _SOURCES.get(source.subject_type)
    if known is not None and (
        known.kind,
        known.read_action,
        known.events,
        getattr(known.open_for, "__qualname__", None),
    ) != (
        source.kind,
        source.read_action,
        source.events,
        getattr(source.open_for, "__qualname__", None),
    ):
        raise ValueError(f"gate subject {source.subject_type!r} is already registered")
    _SOURCES[source.subject_type] = source


def gate_sources() -> tuple[GateSource, ...]:
    return tuple(_SOURCES[k] for k in sorted(_SOURCES))


# --- Reconcile (pure) --------------------------------------------------------------------------


@dataclass(frozen=True)
class Existing:
    id: UUID
    subject_id: UUID
    state: str
    assignee_user_id: UUID | None
    due_on: date | None


@dataclass(frozen=True)
class Plan:
    inserts: tuple[OpenGate, ...]
    # (row id, state, assignee, due on): rows whose stored values differ from the owner's.
    updates: tuple[tuple[UUID, str, UUID | None, date | None], ...]

    @property
    def empty(self) -> bool:
        return not self.inserts and not self.updates


def plan(existing: Sequence[Existing], open_now: Sequence[OpenGate]) -> Plan:
    """What makes the stored rows say what the owner says. A voided row stays voided."""
    waiting = {g.subject_id: g for g in open_now}
    stored = {e.subject_id: e for e in existing}
    inserts = tuple(
        g for s, g in sorted(waiting.items(), key=lambda i: str(i[0])) if s not in stored
    )
    updates: list[tuple[UUID, str, UUID | None, date | None]] = []
    for subject, row in sorted(stored.items(), key=lambda i: str(i[0])):
        if row.state == "voided":
            continue
        gate = waiting.get(subject)
        if gate is None:
            if row.state != "done":
                updates.append((row.id, "done", row.assignee_user_id, row.due_on))
            continue
        wanted = ("open", gate.assignee_user_id, gate.due_on)
        if (row.state, row.assignee_user_id, row.due_on) != wanted:
            updates.append((row.id, *wanted))
    return Plan(inserts, tuple(updates))


def source_event_id(event_id: UUID, subject_type: str, subject_id: UUID) -> UUID:
    """The row's `source_event_id`: the event that opened it, made unique per subject."""
    return uuid.uuid5(_NAMESPACE, f"{event_id}:{subject_type}:{subject_id}")


# --- The projector -----------------------------------------------------------------------------


class _Unchanged(Exception):
    """Nothing to write: leave the unit of work without a commit."""


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "review.human_gates")


def _subject(source: GateSource, subject_id: UUID) -> dict[str, str]:
    return {"type": source.subject_type, "id": str(subject_id)}


async def _stored(
    session: AsyncSession, source: GateSource, engagement_id: UUID | None
) -> list[Existing]:
    stmt = select(HumanGate).where(
        HumanGate.kind == source.kind,
        HumanGate.subject_ref["type"].astext == source.subject_type,
    )
    if engagement_id is not None:
        stmt = stmt.where(HumanGate.engagement_id == engagement_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        Existing(r.id, UUID(r.subject_ref["id"]), r.state, r.assignee_user_id, r.due_on)
        for r in rows
    ]


async def _reconcile(
    tenant_id: UUID, source: GateSource, engagement_id: UUID | None, event_id: UUID
) -> int:
    """One source on one engagement (or all of them); returns the rows written."""
    tenant = _system(tenant_id)
    try:
        async with uow(tenant) as tx:
            key = f"human_gates:{tenant_id}:{source.subject_type}:{engagement_id or '*'}"
            await tx.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
            )
            # Read after the lock: an event committed before us is seen, one after waits.
            open_now = await source.open_for(tenant, engagement_id)
            if engagement_id is not None:
                open_now = [g for g in open_now if g.engagement_id == engagement_id]
            todo = plan(await _stored(tx.session, source, engagement_id), open_now)
            if todo.empty:
                raise _Unchanged
            added = 0
            for gate in todo.inserts:
                found = await tx.session.execute(
                    pg_insert(HumanGate)
                    .values(
                        tenant_id=tenant_id,
                        kind=source.kind,
                        subject_ref=_subject(source, gate.subject_id),
                        engagement_id=gate.engagement_id,
                        work_item_id=gate.work_item_id,
                        client_id=gate.client_id,
                        assignee_user_id=gate.assignee_user_id,
                        role=gate.role,
                        due_on=gate.due_on,
                        state="open",
                        source_event_id=source_event_id(
                            event_id, source.subject_type, gate.subject_id
                        ),
                    )
                    .on_conflict_do_nothing()
                    .returning(HumanGate.id)
                )
                added += len(found.scalars().all())
            for row_id, state, assignee, due_on in todo.updates:
                await tx.session.execute(
                    update(HumanGate)
                    .where(HumanGate.id == row_id)
                    .values(
                        state=state,
                        assignee_user_id=assignee,
                        due_on=due_on,
                        updated_at=system_now(),
                    )
                )
            closed = sum(1 for u in todo.updates if u[1] == "done")
            tx.record(
                "human_gate.projected",
                target=(
                    Target("engagement", engagement_id)
                    if engagement_id is not None
                    else Target("firm", tenant_id)
                ),
                after=Ref(opened=added + len(todo.updates) - closed, closed=closed),
            )
            return added + len(todo.updates)
    except _Unchanged:
        return 0


async def apply_event(event: OutboxEvent) -> None:
    """The `HumanGateProjector` outbox consumer: idempotent on the event (and on its subject)."""
    raw = event.payload.get("engagement_id")
    if raw is None:
        return
    engagement_id = UUID(str(raw))
    for source in gate_sources():
        if event.event_type in source.events:
            await _reconcile(event.tenant_id, source, engagement_id, event.event_id)


async def rebuild_human_gates(tenant_id: UUID) -> int:
    """`review.rebuild_human_gates`: every source over every engagement, from the owners'
    records; an operator command runs it (never a person's request). Returns the rows written."""
    rebuild = uuid.uuid5(_NAMESPACE, f"rebuild:{tenant_id}")
    written = 0
    for source in gate_sources():
        written += await _reconcile(tenant_id, source, None, rebuild)
    _log.info("human_gates.rebuilt", written=written)
    return written


SUBSCRIPTIONS: Mapping[str, Callable[[OutboxEvent], Awaitable[None]]] = {
    event: apply_event for event in sorted(C13_EVENTS)
}


# --- The read (GET /v1/human-gates) ------------------------------------------------------------


@dataclass(frozen=True)
class GateView:
    id: UUID
    kind: str
    subject_type: str
    subject_id: UUID
    engagement_id: UUID | None
    work_item_id: UUID | None
    client_id: UUID | None
    assignee_user_id: UUID | None
    role: str | None
    due_on: date | None
    state: str
    created_at: datetime


def _engagement() -> ColumnElement[UUID]:
    return cast(ColumnElement[UUID], HumanGate.engagement_id.expression)


def _sources_visible(ctx: AuthContext) -> ColumnElement[bool]:
    """Each source's gates where the caller may read its subjects (walls excluded there too)."""
    clauses = [
        and_(
            HumanGate.subject_ref["type"].astext == source.subject_type,
            visible(ctx, source.read_action, _engagement()),
        )
        for source in gate_sources()
    ]
    return or_(*clauses) if clauses else false()


async def gates_waiting_on(
    ctx: AuthContext,
    *,
    kind: str | None,
    engagement_id: UUID | None,
    cursor: str | None,
    limit: int | None,
) -> ListPage[GateView]:
    """Open gates assigned to the caller or to nobody, in engagements the caller may read them
    in, oldest first; `counts` per kind over the same filters without `kind`."""
    size = clamp_limit(limit)
    query = query_hash(kind=kind, engagement_id=engagement_id)
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=query)
        if cursor
        else None
    )
    base = select(HumanGate).where(
        HumanGate.state == "open",
        or_(HumanGate.assignee_user_id == ctx.user_id, HumanGate.assignee_user_id.is_(None)),
        visible(ctx, READ, _engagement()),
        _sources_visible(ctx),
    )
    if engagement_id is not None:
        base = base.where(HumanGate.engagement_id == engagement_id)
    stmt = base.where(HumanGate.kind == kind) if kind is not None else base
    sort = cast(ColumnElement[object], HumanGate.updated_at.expression)
    async with tenant_session(ctx.tenant) as session:
        counts = await status_counts(session, base, cast(ColumnElement[str], HumanGate.kind))
        total = await capped_total(session, stmt)
        fetched = (
            (
                await session.execute(
                    keyset(
                        stmt,
                        sort=sort,
                        id_column=cast(ColumnElement[object], HumanGate.id.expression),
                        after=after,
                        limit=size,
                    )
                )
            )
            .scalars()
            .all()
        )
    rows, position = page_of(fetched, limit=size, key=lambda r: r.updated_at, id_of=lambda r: r.id)
    return envelope(
        [
            GateView(
                r.id,
                r.kind,
                r.subject_ref["type"],
                UUID(r.subject_ref["id"]),
                r.engagement_id,
                r.work_item_id,
                r.client_id,
                r.assignee_user_id,
                r.role,
                r.due_on,
                r.state,
                r.updated_at,
            )
            for r in rows
        ],
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=query,
        total=total,
        counts=counts,
    )


__all__ = [
    "C13_EVENTS",
    "GATE_KINDS",
    "SUBSCRIPTIONS",
    "Existing",
    "GateSource",
    "GateView",
    "OpenGate",
    "Plan",
    "gate_sources",
    "gates_waiting_on",
    "plan",
    "apply_event",
    "rebuild_human_gates",
    "register_gate_source",
    "source_event_id",
]
