"""Ledger rules (ADR-004, ADR-038). PROTECTED. TASK-010 design §5, stages 5 and 6 input.

Snapshots are immutable and exist only for validated trial balances. Recording the same pull
twice returns the first snapshot (one snapshot per pull, §12).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence.api import TrialBalance, TrialBalanceLine
from abacus.modules.ledger.normalise import NormalisedTrialBalance, validate
from abacus.modules.ledger.repository import (
    find_snapshot,
    get_snapshot,
    insert_lines,
    insert_snapshot,
    lines_of,
)


class Unvalidated(ValueError):
    """A trial balance that fails validation can't become a snapshot (ADR-038)."""


@dataclass(frozen=True)
class SnapshotRef:
    id: UUID
    created: bool  # False when this pull's snapshot already existed


async def record_snapshot(
    tx: UnitOfWork,
    *,
    client_entity_id: UUID,
    tb: NormalisedTrialBalance,
    raw_fingerprint: str,
    pulled_at: datetime,
    source: str,
) -> SnapshotRef:
    """Inside the caller's unit of work. Re-validates: nothing unvalidated is ever stored."""
    failure = validate(tb, period_start=tb.period_start, period_end=tb.period_end)
    if failure is not None:
        raise Unvalidated(failure)
    tenant = await transaction_context(tx.session)
    snapshot_id = await insert_snapshot(
        tx.session,
        tenant_id=tenant.tenant_id,
        client_entity_id=client_entity_id,
        period_start=tb.period_start,
        period_end=tb.period_end,
        pulled_at=pulled_at,
        source=source,
        raw_fingerprint=raw_fingerprint,
        line_count=len(tb.lines),
        total_debit=tb.total_debit,
        total_credit=tb.total_credit,
    )
    if snapshot_id is None:
        existing = await find_snapshot(
            tx.session,
            client_entity_id=client_entity_id,
            period_start=tb.period_start,
            period_end=tb.period_end,
            raw_fingerprint=raw_fingerprint,
        )
        if existing is None:  # conflict on a row this transaction can't see: impossible
            raise NotFound("ledger_snapshot")
        return SnapshotRef(existing.id, created=False)
    await insert_lines(tx.session, tenant.tenant_id, snapshot_id, tb.lines)
    tx.record(
        "ledger_snapshot.created",
        target=Target("ledger_snapshot", snapshot_id),
        after=Ref(client_entity_id=client_entity_id, raw_fingerprint=raw_fingerprint),
    )
    return SnapshotRef(snapshot_id, created=True)


async def trial_balance_for(
    tenant: TenantContext, snapshot_id: UUID, *, entity_name: str
) -> TrialBalance:
    """The snapshot as the renderer's input. `entity_name` comes from our own records, never
    the provider."""
    async with tenant_session(tenant) as session:
        snapshot = await get_snapshot(session, snapshot_id)
        if snapshot is None:
            raise NotFound("ledger_snapshot")
        lines = await lines_of(session, snapshot_id)
        return TrialBalance(
            client_entity_id=snapshot.client_entity_id,
            entity_name=entity_name,
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            pulled_at=snapshot.pulled_at,
            snapshot_id=snapshot.id,
            source=snapshot.source,
            source_fingerprint=snapshot.raw_fingerprint,
            lines=tuple(
                TrialBalanceLine(line.account_code, line.account_name, line.debit, line.credit)
                for line in lines
            ),
        )
