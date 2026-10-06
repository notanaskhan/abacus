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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from abacus.kernel.classification import classified, sensitive_paths
from abacus.kernel.db import TenantContext, tenant_connection

_ACTION = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")


class MissingAuditEvent(RuntimeError):
    """A unit of work tried to commit without recording an audit event (ADR-007)."""


@dataclass(frozen=True)
class Target:
    """What an action was done to: an entity type and its identifier."""

    type: str
    id: str | UUID

    def __post_init__(self) -> None:
        if not self.type or not str(self.id):
            raise ValueError("audit target needs a type and an id")


class Ref:
    """A reference to a state (identifiers, versions, fingerprints), never the state itself."""

    def __init__(self, **fields: str | int | UUID) -> None:
        self.fields: dict[str, str | int] = {
            key: str(value) if isinstance(value, UUID) else value for key, value in fields.items()
        }


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
        if self._audit:
            await self._connection.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                    "target_type, target_id, before_ref, after_ref) VALUES (:tenant, :kind, "
                    ":actor, :action, :target_type, :target_id, CAST(:before AS jsonb), "
                    "CAST(:after AS jsonb))"
                ),
                [
                    {
                        "tenant": ctx.tenant_id,
                        "kind": ctx.actor_kind,
                        "actor": ctx.actor_id,
                        "action": a.action,
                        "target_type": a.target.type,
                        "target_id": str(a.target.id),
                        "before": None if a.before is None else json.dumps(a.before.fields),
                        "after": None if a.after is None else json.dumps(a.after.fields),
                    }
                    for a in self._audit
                ],
            )
        if self._events:
            await self._connection.execute(
                text(
                    "INSERT INTO outbox (id, tenant_id, event_type, payload) "
                    "VALUES (:id, :tenant, :event_type, CAST(:payload AS jsonb))"
                ),
                [
                    {
                        "id": e.event_id,
                        "tenant": ctx.tenant_id,
                        "event_type": e.event_type,
                        "payload": e.model_dump_json(),
                    }
                    for e in self._events
                ],
            )


@asynccontextmanager
async def uow(ctx: TenantContext) -> AsyncGenerator[UnitOfWork]:
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


__all__ = ["DomainEvent", "MissingAuditEvent", "Ref", "Target", "UnitOfWork", "uow"]
