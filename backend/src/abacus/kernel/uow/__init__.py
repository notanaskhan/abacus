"""Unit of work: a state change, its audit events and its domain events commit together or not at
all (ADR-007, ADR-018). PROTECTED. TASK-006 design §1-3.

    async with uow(ctx) as tx:
        item = await tx.session.get(RequestItem, item_id)
        item.status = "received"
        tx.record("request_item.received", target=Target("request_item", item.id),
                  before=Ref(version=3), after=Ref(version=4))
        tx.emit(RequestItemReceived(request_item_id=item.id))

No audit event, no commit: leaving the block without a `record` call raises `MissingAuditEvent`
and nothing is written. Read-only work uses `tenant_session` instead.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, ClassVar, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, DateTime, Select, Text, column, select, table, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from abacus.kernel import request_context
from abacus.kernel.classification import classified, sensitive_paths
from abacus.kernel.db import TenantContext, tenant_connection
from abacus.kernel.telemetry import current_trace_id, current_traceparent
from abacus.kernel.uow.relay import Handler, OutboxEvent, payload_sha256

_ACTION = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")
_TYPE = re.compile(r"[a-z][a-z_]*")
_REF_KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_DIGITS = re.compile(r"[0-9]+")
_active: ContextVar[bool] = ContextVar("abacus_uow_active", default=False)


def _identifier(value: object) -> str:
    """A UUID or an integer, as text. Audit targets are identifiers, never free text."""
    if isinstance(value, bool):
        raise ValueError("audit identifiers are UUIDs or integers")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if _DIGITS.fullmatch(value):
            return value
        try:
            return str(UUID(value))
        except ValueError:
            pass
    raise ValueError("audit identifiers are UUIDs or integers")


class MissingAuditEvent(RuntimeError):
    """A unit of work tried to commit without recording an audit event (ADR-007)."""


@dataclass(frozen=True)
class Target:
    """What an action was done to: an entity type and its identifier."""

    type: str
    id: str | int | UUID

    def __post_init__(self) -> None:
        if not _TYPE.fullmatch(self.type):
            raise ValueError(f"audit target type {self.type!r} must match {_TYPE.pattern}")
        _identifier(self.id)


class Ref:
    """A reference to a state (identifiers, versions, fingerprints), never the state itself."""

    def __init__(self, **fields: str | int | UUID) -> None:
        self.fields: dict[str, str | int] = {}
        for key, value in fields.items():
            if not _REF_KEY.fullmatch(key):
                raise ValueError(f"reference key {key!r} must match {_REF_KEY.pattern}")
            self.fields[key] = _ref_value(value)


def _ref_value(value: object) -> str | int:
    """UUIDs, integers and SHA-256 fingerprints only: a reference can never carry free text."""
    if isinstance(value, bool):
        raise ValueError("reference values are UUIDs, integers or SHA-256 fingerprints")
    if isinstance(value, int):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str) and _FINGERPRINT.fullmatch(value):
        return value
    raise ValueError("reference values are UUIDs, integers or SHA-256 fingerprints")


class DomainEvent(BaseModel):
    """Announces a state change to other modules. Carries identifiers only (no Restricted data);
    consumers load what they need under their own tenant context. Subclasses set `event_type`."""

    model_config = ConfigDict(frozen=True)

    event_type: ClassVar[str]
    event_id: Annotated[UUID, classified("internal")] = Field(default_factory=uuid4)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: object) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        if not isinstance(cls.__dict__.get("event_type"), str):
            raise TypeError(f"{cls.__name__} must define event_type: ClassVar[str]")


def event_sha256(event: DomainEvent) -> str:
    """The digest a grant-held event is delivered under (P-04-T10): issue its grant with this, and
    the relay recomputes it from the stored payload."""
    return payload_sha256(cast(dict[str, object], json.loads(event.model_dump_json())))


@dataclass(frozen=True)
class Scope:
    """What an audit event is scoped to (Q-02-T16): the explorer filters on it exactly."""

    engagement_id: UUID | None = None
    work_item_id: UUID | None = None


@dataclass(frozen=True)
class _AuditEvent:
    action: str
    target: Target
    before: Ref | None
    after: Ref | None
    scope: Scope | None = None


@dataclass
class UnitOfWork:
    session: AsyncSession
    _connection: AsyncConnection
    _audit: list[_AuditEvent] = field(default_factory=list[_AuditEvent])
    _events: list[DomainEvent] = field(default_factory=list[DomainEvent])
    # P-06-T06: per event, when it may be delivered and the approval grant that holds it.
    _held: dict[UUID, tuple[datetime | None, UUID | None]] = field(
        default_factory=dict[UUID, tuple[datetime | None, UUID | None]]
    )

    def record(
        self,
        action: str,
        *,
        target: Target,
        before: Ref | None = None,
        after: Ref | None = None,
        scope: Scope | None = None,
    ) -> None:
        if not _ACTION.fullmatch(action):
            raise ValueError(f"audit action {action!r} must look like 'entity.verb_past'")
        self._audit.append(_AuditEvent(action, target, before, after, scope))

    def emit(
        self,
        event: DomainEvent,
        *,
        not_before: datetime | None = None,
        grant_id: UUID | None = None,
    ) -> None:
        """Queue `event` for the relay. `not_before` holds delivery until then (an Undo window);
        `grant_id` makes it a grant-held effect, delivered only if the grant is consumed at
        delivery (ADR-161; P-06-T06)."""
        if not_before is not None and not_before.tzinfo is None:
            raise ValueError("not_before needs a time zone")
        if not_before is not None or grant_id is not None:
            self._held[event.event_id] = (not_before, grant_id)
        sensitive = sensitive_paths(event)
        if sensitive:
            raise ValueError(
                f"{type(event).__name__} carries Restricted or unclassified data "
                f"({', '.join(sensitive)}); domain events carry identifiers only"
            )
        self._events.append(event)

    async def _request_context(self, ctx: TenantContext) -> dict[str, object]:
        """G-02-T06 (SPEC-349 AC-9): the request a person or a support engineer acted through.
        Agent, system and policy events carry none (and the database refuses them)."""
        found = request_context.current()
        keys = ("ip", "ua_family", "device", "session", "auth_method", "mfa_at")
        empty: dict[str, object] = {key: None for key in keys}
        if found is None or ctx.actor_kind not in request_context.PERSON_KINDS:
            return empty
        session_id, mfa_at = found.session_id, found.mfa_at
        resolver = request_context.session_resolver()
        if (
            session_id is None
            and ctx.actor_kind == "human"
            and found.session_cookie_sha256 is not None
            and resolver is not None
        ):
            try:
                actor = UUID(ctx.actor_id)
            except ValueError:
                actor = None
            resolved = (
                await resolver(self._connection, found.session_cookie_sha256, actor)
                if actor is not None
                else None
            )
            if resolved is not None:
                session_id = resolved.session_id
                mfa_at = mfa_at or resolved.mfa_at
        return {
            "ip": found.ip,
            "ua_family": found.user_agent_family,
            "device": found.device_label,
            "session": session_id,
            "auth_method": "support" if ctx.actor_kind == "support" else found.auth_method,
            "mfa_at": mfa_at,
        }

    async def _write(self, ctx: TenantContext) -> None:
        # Every row can be followed to its trace (ADR-007; TASK-013).
        trace_id = current_trace_id()
        if self._audit:
            context = await self._request_context(ctx)
            await self._connection.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                    "target_type, target_id, before_ref, after_ref, trace_id, engagement_id, "
                    "work_item_id, on_behalf_of_user_id, ip, user_agent_family, device_label, "
                    "session_id, auth_method, mfa_at) VALUES (:tenant, :kind, :actor, "
                    ":action, :target_type, :target_id, CAST(:before AS jsonb), "
                    "CAST(:after AS jsonb), :trace_id, :engagement, :work_item, :on_behalf_of, "
                    "CAST(:ip AS inet), :ua_family, :device, :session, :auth_method, :mfa_at)"
                ),
                [
                    {
                        **context,
                        "tenant": ctx.tenant_id,
                        "kind": ctx.actor_kind,
                        "actor": ctx.actor_id,
                        "action": a.action,
                        "target_type": a.target.type,
                        "target_id": _identifier(a.target.id),
                        "before": None if a.before is None else json.dumps(a.before.fields),
                        "after": None if a.after is None else json.dumps(a.after.fields),
                        "trace_id": trace_id,
                        "engagement": a.scope.engagement_id if a.scope else None,
                        "work_item": a.scope.work_item_id if a.scope else None,
                        "on_behalf_of": ctx.on_behalf_of_user_id,
                    }
                    for a in self._audit
                ],
            )
        if self._events:
            await self._connection.execute(
                text(
                    "INSERT INTO outbox (id, tenant_id, event_type, payload, trace_context, "
                    "not_before, grant_id) VALUES (:id, :tenant, :event_type, "
                    "CAST(:payload AS jsonb), :trace_context, :not_before, :grant_id)"
                ),
                [
                    {
                        "id": e.event_id,
                        "tenant": ctx.tenant_id,
                        "event_type": e.event_type,
                        "payload": e.model_dump_json(),
                        "trace_context": current_traceparent(),
                        "not_before": self._held.get(e.event_id, (None, None))[0],
                        "grant_id": self._held.get(e.event_id, (None, None))[1],
                    }
                    for e in self._events
                ],
            )


@asynccontextmanager
async def uow(ctx: TenantContext) -> AsyncGenerator[UnitOfWork]:
    if _active.get():
        # A second uow would be a second connection and transaction: its commit would survive the
        # outer one's rollback, and the two could deadlock. One state change, one unit of work.
        raise RuntimeError("nested unit of work")
    token = _active.set(True)
    try:
        async with _unit_of_work(ctx) as work:
            yield work
    finally:
        _active.reset(token)


@asynccontextmanager
async def _unit_of_work(ctx: TenantContext) -> AsyncGenerator[UnitOfWork]:
    async with tenant_connection(ctx) as conn:
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            autoflush=True,
            join_transaction_mode="rollback_only",
        )
        work = UnitOfWork(session, conn)
        try:
            yield work
            if not work._audit:  # pyright: ignore[reportPrivateUsage] -- same module
                raise MissingAuditEvent(
                    "a unit of work must record at least one audit event before it commits"
                )
            await session.flush()
            await work._write(ctx)  # pyright: ignore[reportPrivateUsage] -- same module
            await conn.commit()
        except BaseException:
            await conn.rollback()
            raise
        finally:
            await session.close()


@dataclass(frozen=True)
class AuditFilter:
    """SPEC-304 (TASK-305): what the audit log explorer narrows to; None means any."""

    action: str | None = None
    actor_kind: str | None = None
    actor_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None


@dataclass(frozen=True)
class AuditRow:
    seq: int
    occurred_at: datetime
    actor_kind: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    before_ref: dict[str, str | int] | None
    after_ref: dict[str, str | int] | None
    trace_id: str | None


async def audit_page(
    session: AsyncSession, where: AuditFilter, before_seq: int | None, limit: int
) -> list[AuditRow]:
    """The active tenant's trail, newest first, `limit` rows older than `before_seq` (SPEC-304).
    The audit trail's owner answers; the caller has authorised the read. Static SQL: a filter
    left as NULL matches every row."""
    rows = await session.execute(
        text(
            "SELECT seq, occurred_at, actor_kind, actor_id, action, target_type, target_id, "
            "before_ref, after_ref, trace_id FROM audit_events WHERE "
            "(CAST(:action AS text) IS NULL OR action = :action) "
            "AND (CAST(:actor_kind AS text) IS NULL OR actor_kind = :actor_kind) "
            "AND (CAST(:actor_id AS text) IS NULL OR actor_id = :actor_id) "
            "AND (CAST(:target_type AS text) IS NULL OR target_type = :target_type) "
            "AND (CAST(:target_id AS text) IS NULL OR target_id = :target_id) "
            "AND (CAST(:since AS timestamptz) IS NULL OR occurred_at >= :since) "
            "AND (CAST(:until AS timestamptz) IS NULL OR occurred_at < :until) "
            "AND (CAST(:before_seq AS bigint) IS NULL OR seq < :before_seq) "
            "ORDER BY seq DESC LIMIT :limit"
        ),
        {
            "action": where.action,
            "actor_kind": where.actor_kind,
            "actor_id": where.actor_id,
            "target_type": where.target_type,
            "target_id": where.target_id,
            "since": where.since,
            "until": where.until,
            "before_seq": before_seq,
            "limit": limit,
        },
    )
    return [AuditRow(*row) for row in rows.all()]


async def audit_facets(session: AsyncSession) -> tuple[list[str], list[str]]:
    """The distinct actions and target types in the active tenant's trail (SPEC-304)."""
    actions = await session.execute(text("SELECT DISTINCT action FROM audit_events ORDER BY 1"))
    types = await session.execute(text("SELECT DISTINCT target_type FROM audit_events ORDER BY 1"))
    return [str(a) for (a,) in actions.all()], [str(t) for (t,) in types.all()]


__all__ = [
    "AuditFilter",
    "AuditRow",
    "DomainEvent",
    "Handler",
    "MissingAuditEvent",
    "OutboxEvent",
    "Ref",
    "Scope",
    "Target",
    "TargetEvent",
    "UnitOfWork",
    "audit_acted_since",
    "audit_activity",
    "audit_facets",
    "audit_of_targets",
    "audit_page",
    "audit_total_of_targets",
    "event_sha256",
    "payload_sha256",
    "uow",
]


async def audit_counts(
    session: AsyncSession, action: str, target_type: str, target_ids: Sequence[UUID]
) -> dict[UUID, int]:
    """How many `action` events each target has in the active tenant's trail (SPEC-012: requests
    per support session). The audit trail's owner answers; modules never query it directly."""
    if not target_ids:
        return {}
    rows = await session.execute(
        text(
            "SELECT target_id, count(*) FROM audit_events WHERE action = :action "
            "AND target_type = :type AND target_id = ANY(:ids) GROUP BY target_id"
        ),
        {"action": action, "type": target_type, "ids": [str(i) for i in target_ids]},
    )
    return {UUID(str(target)): int(count) for target, count in rows.all()}


@dataclass(frozen=True)
class TargetEvent:
    """One audit event about a target, identifiers only (P-06-T07: an activity tab)."""

    id: UUID
    seq: int
    at: datetime  # business time (`effective_at`)
    actor_kind: str
    actor_id: str
    on_behalf_of_user_id: UUID | None
    action: str
    target_type: str
    target_id: str
    after_ref: dict[str, str | int] | None


async def audit_of_targets(
    session: AsyncSession,
    targets: Sequence[tuple[str, UUID]],
    before_seq: int | None,
    limit: int,
    *,
    action: str | None = None,
) -> list[TargetEvent]:
    """The active tenant's events about any of `targets` (type, id), newest first, `limit` rows
    older than `before_seq`, optionally one `action` only. The audit trail's owner answers; the
    caller has authorised the read of every target (an activity tab of a record it may read)."""
    if not targets:
        return []
    rows = await session.execute(
        text(
            "SELECT id, seq, effective_at, actor_kind, actor_id, on_behalf_of_user_id, action, "
            "target_type, target_id, after_ref FROM audit_events "
            "WHERE (target_type, target_id) IN (SELECT * FROM unnest("
            "CAST(:types AS text[]), CAST(:ids AS text[]))) "
            "AND (CAST(:action AS text) IS NULL OR action = :action) "
            "AND (CAST(:before_seq AS bigint) IS NULL OR seq < :before_seq) "
            "ORDER BY seq DESC LIMIT :limit"
        ),
        {
            "types": [t for t, _ in targets],
            "ids": [str(i) for _, i in targets],
            "action": action,
            "before_seq": before_seq,
            "limit": limit,
        },
    )
    return [TargetEvent(*row) for row in rows.all()]


async def audit_acted_since(
    session: AsyncSession,
    targets: Sequence[tuple[str, UUID]],
    actions: Sequence[str],
    since: datetime,
) -> bool:
    """Whether the active tenant's audit trail holds one of `actions` about any of `targets`
    after `since` (business time), however many other events there are (R-01-T08: a client's
    Undo closes once the firm acted). The caller has authorised a read of the targets."""
    if not targets or not actions:
        return False
    found = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM audit_events "
            "WHERE (target_type, target_id) IN (SELECT * FROM unnest("
            "CAST(:types AS text[]), CAST(:ids AS text[]))) "
            "AND action = ANY(CAST(:actions AS text[])) AND effective_at > :since)"
        ),
        {
            "types": [t for t, _ in targets],
            "ids": [str(i) for _, i in targets],
            "actions": list(actions),
            "since": since,
        },
    )
    return bool(found)


_audit_events = table(
    "audit_events",
    column("seq", BigInteger),
    column("engagement_id", PgUUID(as_uuid=True)),
    column("target_type", Text),
    column("target_id", Text),
    column("effective_at", DateTime(timezone=True)),
    column("action", Text),
)


def audit_activity() -> Select[int, UUID | None, str, str, datetime, str]:
    """Every event's `(seq, engagement_id, target_type, target_id, effective_at, action)`, as a
    subquery for a caller composing "last activity" over records it may read (P-07-T08: the
    clients index). Identifiers only; RLS keeps it to the active tenant."""
    c = _audit_events.c
    return cast(
        Select[int, UUID | None, str, str, datetime, str],
        select(c.seq, c.engagement_id, c.target_type, c.target_id, c.effective_at, c.action),
    )


async def audit_total_of_targets(
    session: AsyncSession, targets: Sequence[tuple[str, UUID]], cap: int = 10_000
) -> tuple[int, bool]:
    """How many events `audit_of_targets` would list in all, exact up to `cap` (P-36 totals)."""
    if not targets:
        return 0, False
    n = int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM (SELECT 1 FROM audit_events "
                    "WHERE (target_type, target_id) IN (SELECT * FROM unnest("
                    "CAST(:types AS text[]), CAST(:ids AS text[]))) LIMIT :cap) capped"
                ),
                {
                    "types": [t for t, _ in targets],
                    "ids": [str(i) for _, i in targets],
                    "cap": cap + 1,
                },
            )
        ).scalar_one()
    )
    return (cap, True) if n > cap else (n, False)
