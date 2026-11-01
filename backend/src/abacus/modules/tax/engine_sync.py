"""The engine-sync read model and gates (T-01-T27; T-01 §3.9; tax-engine-bridge §3, §5; C13; C16;
DEC-1463). RED: it decides what a person sees about what left the firm.

- **The chip** is a pure function of facts read in one statement (`chip_facts`): a pending import
  waits on a person first; then an engine error (a diagnostics run with errors, or an export that
  failed); then a generated export nobody has marked; then the last sync, out of sync if Accrued
  changed a field after it; then a final approval with nothing exported yet; else never exported.
  The seven states are the registry's `return_sync_chip`, and `chip_state` covers each.
- **Gate kinds** (C13 `register_gate_kind`): `import_pending_approval` is met when no return on the
  engagement has an import waiting on a person; `ready_to_transmit` when every return is approved
  or later and synced (marked exported, nothing changed since).
- **Notification kinds** (C16, registered in the notifications catalogue): `ready_to_transmit`,
  `efile_relocked` and `ack_rejected`, and the engine's source for the existing `export_failed`,
  each from its outbox event,
  to the people the producer names (`recipient_user_ids`, never the actor). `efile_relocked` and
  `ack_rejected` fan out once their
  producers land (T-02's e-file lock and T-01-T26's acknowledgements).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import DomainEvent
from abacus.modules.integrations.api import register_last_engine_sync
from abacus.modules.review.api import register_gate_kind

SyncState = Literal[
    "not_yet_exported",
    "ready_for_export",
    "exporting",
    "synced",
    "out_of_sync",
    "import_pending_approval",
    "failed",
]
APPROVED_OR_LATER: Final = frozenset({"approved", "awaiting_signature", "filed", "accepted"})


@dataclass(frozen=True)
class ChipFacts:
    pending_import: bool
    diagnostics_errors: int
    export_failed: bool
    unmarked_export: bool
    last_synced_at: datetime | None
    changed_since_sync: bool
    final_approved: bool


def chip_state(facts: ChipFacts) -> SyncState:
    """TAX-09's chip from its facts (code, never stored)."""
    if facts.pending_import:
        return "import_pending_approval"
    if facts.diagnostics_errors > 0 or facts.export_failed:
        return "failed"
    if facts.unmarked_export:
        return "exporting"
    if facts.last_synced_at is not None:
        return "out_of_sync" if facts.changed_since_sync else "synced"
    if facts.final_approved:
        return "ready_for_export"
    return "not_yet_exported"


# One statement: the return's status, a waiting import, the latest diagnostics run's errors, an
# unmarked export, and the last sync (an approved import or a marked export).
_FACTS = text(
    """
    SELECT
        r.status,
        EXISTS (
            SELECT 1 FROM engine_import_diffs d
            WHERE d.return_id = r.work_item_id AND d.status = 'pending_approval'
        ) AS pending_import,
        COALESCE((
            SELECT (e.summary ->> 'errors')::int FROM engine_sync_events e
            WHERE e.return_id = r.work_item_id AND e.kind = 'diagnostics'
            ORDER BY e.at DESC LIMIT 1
        ), 0) AS diagnostics_errors,
        EXISTS (
            SELECT 1 FROM engine_exports x
            WHERE x.return_id = r.work_item_id AND x.marked_exported_at IS NULL
        ) AS unmarked_export,
        (
            SELECT max(e.at) FROM engine_sync_events e
            WHERE e.return_id = r.work_item_id AND e.kind IN ('import_approved', 'marked_exported')
        ) AS last_synced_at
    FROM tax_returns r WHERE r.work_item_id = :r
    """
)


@dataclass(frozen=True)
class ReturnSyncFacts:
    status: str
    pending_import: bool
    diagnostics_errors: int
    unmarked_export: bool
    last_synced_at: datetime | None


async def sync_facts(session: AsyncSession, return_id: UUID) -> ReturnSyncFacts | None:
    row = (await session.execute(_FACTS, {"r": return_id})).first()
    if row is None:
        return None
    return ReturnSyncFacts(
        str(row.status),
        bool(row.pending_import),
        int(row.diagnostics_errors or 0),
        bool(row.unmarked_export),
        cast(datetime | None, row.last_synced_at),
    )


def facts_for(found: ReturnSyncFacts, *, changed_since_sync: bool) -> ChipFacts:
    return ChipFacts(
        pending_import=found.pending_import,
        diagnostics_errors=found.diagnostics_errors,
        export_failed=False,
        unmarked_export=found.unmarked_export,
        last_synced_at=found.last_synced_at,
        changed_since_sync=changed_since_sync,
        final_approved=found.status in APPROVED_OR_LATER,
    )


async def return_synced(tenant: TenantContext, return_id: UUID) -> bool:
    """T-01-T37: the return's chip reads Synced (the transmission record requires it)."""
    from abacus.modules.review.api import changed_since

    async with tenant_session(tenant) as session:
        found = await sync_facts(session, return_id)
    if found is None:
        return False
    changed = found.last_synced_at is not None and bool(
        await changed_since(tenant, "tax_return", return_id, found.last_synced_at)
    )
    return chip_state(facts_for(found, changed_since_sync=changed)) == "synced"


# --- C13 gate kinds -----------------------------------------------------------------------------

_RETURNS = text(
    "SELECT work_item_id FROM tax_returns WHERE engagement_id = :e ORDER BY work_item_id"
)


async def no_pending_import(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`import_pending_approval`: met when no return on the engagement waits on an import."""
    async with tenant_session(tenant) as session:
        waiting = await session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM engine_import_diffs d JOIN tax_returns r "
                "ON r.work_item_id = d.return_id WHERE r.engagement_id = :e "
                "AND d.status = 'pending_approval')"
            ),
            {"e": engagement_id},
        )
    return not bool(waiting)


async def ready_to_transmit(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`ready_to_transmit`: every return on the engagement approved or later and synced."""
    from abacus.modules.review.api import changed_since

    async with tenant_session(tenant) as session:
        ids = [
            cast(UUID, r)
            for r in (await session.execute(_RETURNS, {"e": engagement_id})).scalars()
        ]
        found = [await sync_facts(session, i) for i in ids]
    if not ids:
        return False
    for return_id, facts in zip(ids, found, strict=True):
        if facts is None or facts.status not in APPROVED_OR_LATER or facts.last_synced_at is None:
            return False
        if facts.pending_import or facts.unmarked_export or facts.diagnostics_errors:
            return False
        if await changed_since(tenant, "tax_return", return_id, facts.last_synced_at):
            return False
    return True


# --- C16 notification kinds -----------------------------------------------------------------


class EngineSyncFailed(DomainEvent):
    """The engine reported errors for a return (identifiers and counts only)."""

    event_type: ClassVar[str] = "engine_sync.failed"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    errors: Annotated[int, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


class ReadyToTransmit(DomainEvent):
    """A return's workbook reached the engine: it is ready to transmit from the engine."""

    event_type: ClassVar[str] = "tax_return.ready_to_transmit"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


_LAST_SYNCED = text(
    "SELECT return_id FROM engine_sync_events "
    "WHERE kind IN ('import_approved', 'marked_exported') ORDER BY at DESC, id DESC LIMIT 1"
)


async def last_synced_return(tenant: TenantContext) -> UUID | None:
    """T-01-T51: the firm's most recently synced return (an approved import or a marked export),
    for ADM-08's Last sync link; an identifier only."""
    async with tenant_session(tenant) as session:
        found = (await session.execute(_LAST_SYNCED)).scalar_one_or_none()
    return cast(UUID | None, found)


def register() -> None:
    """At import: the two gate kinds (C13) and ADM-08's last-sync source (T-01-T51). The
    notification kinds and their sources are the notifications catalogue's (tax may not import
    notifications, ADR-008)."""
    register_gate_kind("import_pending_approval", no_pending_import)
    register_gate_kind("ready_to_transmit", ready_to_transmit)
    register_last_engine_sync(last_synced_return)


__all__ = [
    "ChipFacts",
    "EngineSyncFailed",
    "ReadyToTransmit",
    "ReturnSyncFacts",
    "SyncState",
    "chip_state",
    "facts_for",
    "no_pending_import",
    "ready_to_transmit",
    "register",
    "sync_facts",
]
