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
from typing import Annotated, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from abacus.kernel.classification import classified, sensitive_paths
from abacus.kernel.db import TenantContext, tenant_connection
from abacus.kernel.telemetry import current_trace_id, current_traceparent
from abacus.kernel.uow.relay import Handler, OutboxEvent

_ACTION = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")
_TYPE = re.compile(r"[a-z][a-z_]*")
_REF_KEY = re.compile(r"[a-z][a-z_]{0,39}")
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


@dataclass(frozen=True)
class _AuditEvent:
    action: str
    target: Target
    before: Ref | None
    after: Ref | None


@dataclass
class UnitOfWork:
    session: AsyncSession
    _connection: AsyncConnection
    _audit: list[_AuditEvent] = field(default_factory=list[_AuditEvent])
    _events: list[DomainEvent] = field(default_factory=list[DomainEvent])

    def record(
        self, action: str, *, target: Target, before: Ref | None = None, after: Ref | None = None
    ) -> None:
        if not _ACTION.fullmatch(action):
            raise ValueError(f"audit action {action!r} must look like 'entity.verb_past'")
        self._audit.append(_AuditEvent(action, target, before, after))

    def emit(self, event: DomainEvent) -> None:
        sensitive = sensitive_paths(event)
        if sensitive:
            raise ValueError(
                f"{type(event).__name__} carries Restricted or unclassified data "
                f"({', '.join(sensitive)}); domain events carry identifiers only"
            )
        self._events.append(event)

    async def _write(self, ctx: TenantContext) -> None:
        # Every row can be followed to its trace (ADR-007; TASK-013).
        trace_id = current_trace_id()
        if self._audit:
            await self._connection.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                    "target_type, target_id, before_ref, after_ref, trace_id) VALUES (:tenant, "
                    ":kind, :actor, :action, :target_type, :target_id, CAST(:before AS jsonb), "
                    "CAST(:after AS jsonb), :trace_id)"
                ),
                [
                    {
                        "tenant": ctx.tenant_id,
                        "kind": ctx.actor_kind,
                        "actor": ctx.actor_id,
                        "action": a.action,
                        "target_type": a.target.type,
                        "target_id": _identifier(a.target.id),
                        "before": None if a.before is None else json.dumps(a.before.fields),
                        "after": None if a.after is None else json.dumps(a.after.fields),
                        "trace_id": trace_id,
                    }
                    for a in self._audit
                ],
            )
        if self._events:
            await self._connection.execute(
                text(
                    "INSERT INTO outbox (id, tenant_id, event_type, payload, trace_context) "
                    "VALUES (:id, :tenant, :event_type, CAST(:payload AS jsonb), :trace_context)"
                ),
                [
                    {
                        "id": e.event_id,
                        "tenant": ctx.tenant_id,
                        "event_type": e.event_type,
                        "payload": e.model_dump_json(),
                        "trace_context": current_traceparent(),
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


__all__ = [
    "DomainEvent",
    "Handler",
    "MissingAuditEvent",
    "OutboxEvent",
    "Ref",
    "Target",
    "UnitOfWork",
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
