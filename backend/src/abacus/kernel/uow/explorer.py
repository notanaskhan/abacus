"""The audit trail's composed read surface (G-02-T08; SPEC-349 §4, §7). PROTECTED.

`audit_events` belongs to the unit of work; the audit_trail module owns its read side (ADM-07).
It composes its list and detail queries over this Core table, as a caller of `audit_activity()`
composes over its subquery, so no module names the kernel's tables in SQL (ADR-008, OWN-001).
Read-only: nothing here writes, and row-level security keeps every read to the active tenant.

`leaf_version_at` answers the leaf version an event is (or will be) sealed under, so the
explorer's `content_hash` is the leaf its checkpoint proves (P-43).
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.uow.chain import LEAF_VERSION

_metadata = MetaData()

AUDIT_EVENTS: Final = Table(
    "audit_events",
    _metadata,
    Column("id", PgUUID(as_uuid=True)),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("seq", BigInteger),
    Column("occurred_at", DateTime(timezone=True)),
    Column("effective_at", DateTime(timezone=True)),
    Column("actor_kind", Text),
    Column("actor_id", Text),
    Column("action", Text),
    Column("target_type", Text),
    Column("target_id", Text),
    Column("before_ref", JSONB),
    Column("after_ref", JSONB),
    Column("trace_id", Text),
    Column("engagement_id", PgUUID(as_uuid=True)),
    Column("work_item_id", PgUUID(as_uuid=True)),
    Column("on_behalf_of_user_id", PgUUID(as_uuid=True)),
    Column("policy_ref", Text),
    Column("ip", INET),
    Column("user_agent_family", Text),
    Column("device_label", Text),
    Column("session_id", PgUUID(as_uuid=True)),
    Column("auth_method", Text),
    Column("mfa_at", DateTime(timezone=True)),
    Column("client_id", PgUUID(as_uuid=True)),
    Column("office_id", PgUUID(as_uuid=True)),
)

_CHECKPOINTS: Final = Table(
    "audit_checkpoints",
    _metadata,
    Column("seq_from", BigInteger),
    Column("seq_to", BigInteger),
    Column("leaf_version", Integer),
)


async def leaf_version_at(session: AsyncSession, seq: int) -> int:
    """The leaf version of the checkpoint sealing `seq`; the current version while unsealed."""
    c = _CHECKPOINTS.c
    found = await session.scalar(
        select(c.leaf_version).where(c.seq_from <= seq, c.seq_to >= seq).limit(1)
    )
    return int(found) if found is not None else LEAF_VERSION


__all__ = ["AUDIT_EVENTS", "leaf_version_at"]
