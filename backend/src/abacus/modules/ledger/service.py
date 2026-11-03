"""Ledger rules (ADR-004, ADR-038). PROTECTED. TASK-010 design §5, stages 5 and 6 input.

Snapshots are immutable and exist only for validated trial balances. Recording the same pull
twice returns the first snapshot (one snapshot per pull, §12).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.ledger.normalise import NormalisedTrialBalance, validate
from abacus.modules.ledger.repository import (
    accounts_in_firm,
    find_snapshot,
    get_snapshot,
    insert_lines,
    insert_snapshot,
    line_of,
    lines_of,
    lines_of_snapshots,
    totals_of_snapshots,
)


class Unvalidated(ValueError):
    """A trial balance that fails validation can't become a snapshot (ADR-038)."""


@dataclass(frozen=True)
class SnapshotLine:
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class SnapshotView:
    """A stored snapshot, read back (ledger's own read model; callers map it as they need)."""

    id: UUID
    client_entity_id: UUID
    period_start: date
    period_end: date
    pulled_at: datetime
    source: str
    raw_fingerprint: str
    lines: tuple[SnapshotLine, ...]


@dataclass(frozen=True)
class SnapshotRef:
    id: UUID
    created: bool  # False when this pull's snapshot already existed


async def record_snapshot(
    tx: UnitOfWork,
    *,
    client_entity_id: UUID,
    period_start: date,
    period_end: date,
    tb: NormalisedTrialBalance,
    raw_fingerprint: str,
    pulled_at: datetime,
    source: str,
) -> SnapshotRef:
    """Inside the caller's unit of work. Re-validates against the requested period: nothing
    unvalidated is ever stored."""
    failure = validate(tb, period_start=period_start, period_end=period_end)
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


DOCUMENT_SOURCE = "document_extraction"


class LineUnverified(DomainInvalid):
    """ADR P-58: every line of a document-extracted TB is cited and code-verified (C4)."""

    code = "line_unverified"


class DocumentUnbalanced(DomainInvalid):
    """The extracted lines do not foot (debits = credits, and to the declared totals)."""

    code = "document_unbalanced"


# The caller's C4 check: which of these citations are verified and live on the engagement
# (`evidence.api.supported_citations`), passed in so the ledger never imports evidence.
CitationCheck = Callable[[Sequence[UUID]], Awaitable[frozenset[UUID]]]


async def record_document_snapshot(
    tx: UnitOfWork,
    *,
    client_entity_id: UUID,
    period_start: date,
    period_end: date,
    tb: NormalisedTrialBalance,
    line_citations: Mapping[str, UUID],
    source_evidence_version_id: UUID,
    extraction_run_id: UUID,
    pulled_at: datetime,
    supported: CitationCheck,
) -> SnapshotRef:
    """ADR P-58 (A-05-T28): a trial balance read from a document becomes a snapshot only when
    code foots it and every line's citation (keyed by the line's `source_ref`) is verified
    through C4. The snapshot names its document and extraction run; it is never adopted here
    (adoption is A-02's human-only TB-of-record version)."""
    if tb.total_debit != tb.total_credit or validate(
        tb, period_start=period_start, period_end=period_end
    ):
        raise DocumentUnbalanced  # facts are identifiers only: no amounts in an error
    missing = [line.account_code for line in tb.lines if line.source_ref not in line_citations]
    if missing:
        raise LineUnverified(facts={"account_code": missing[0]})
    cited = [line_citations[line.source_ref] for line in tb.lines]
    verified = await supported(cited)
    for line, citation in zip(tb.lines, cited, strict=True):
        if citation not in verified:
            raise LineUnverified(facts={"account_code": line.account_code})
    # Each stored line keeps its citation as its source reference (the provenance AUD-06 shows).
    lines = tuple(
        replace(line, source_ref=f"citation:{line_citations[line.source_ref]}")
        for line in tb.lines
    )
    stored = replace(tb, lines=lines)
    body = "|".join(
        [str(source_evidence_version_id), str(extraction_run_id)]
        + [f"{x.account_code}:{x.debit}:{x.credit}:{x.source_ref}" for x in lines]
    )
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    tenant = await transaction_context(tx.session)
    snapshot_id = await insert_snapshot(
        tx.session,
        tenant_id=tenant.tenant_id,
        client_entity_id=client_entity_id,
        period_start=stored.period_start,
        period_end=stored.period_end,
        pulled_at=pulled_at,
        source=DOCUMENT_SOURCE,
        raw_fingerprint=fingerprint,
        line_count=len(lines),
        total_debit=stored.total_debit,
        total_credit=stored.total_credit,
        source_evidence_version_id=source_evidence_version_id,
        extraction_run_id=extraction_run_id,
    )
    if snapshot_id is None:
        existing = await find_snapshot(
            tx.session,
            client_entity_id=client_entity_id,
            period_start=stored.period_start,
            period_end=stored.period_end,
            raw_fingerprint=fingerprint,
        )
        if existing is None:
            raise NotFound("ledger_snapshot")
        return SnapshotRef(existing.id, created=False)
    await insert_lines(tx.session, tenant.tenant_id, snapshot_id, lines)
    tx.record(
        "ledger_snapshot.created",
        target=Target("ledger_snapshot", snapshot_id),
        after=Ref(client_entity_id=client_entity_id, raw_fingerprint=fingerprint),
    )
    return SnapshotRef(snapshot_id, created=True)


async def snapshot_view(tenant: TenantContext, snapshot_id: UUID) -> SnapshotView:
    async with tenant_session(tenant) as session:
        snapshot = await get_snapshot(session, snapshot_id)
        if snapshot is None:
            raise NotFound("ledger_snapshot")
        lines = await lines_of(session, snapshot_id)
        return SnapshotView(
            id=snapshot.id,
            client_entity_id=snapshot.client_entity_id,
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            pulled_at=snapshot.pulled_at,
            source=snapshot.source,
            raw_fingerprint=snapshot.raw_fingerprint,
            lines=tuple(
                SnapshotLine(line.account_code, line.account_name, line.debit, line.credit)
                for line in lines
            ),
        )


@dataclass(frozen=True)
class ScopeFacts:
    """What an engagement's ledger puts in scope (SPEC-006 AC-8): account codes and names, and
    every amount in cents (line debits and credits, and the snapshots' totals)."""

    codes: frozenset[str]
    names: frozenset[str]
    amounts_cents: frozenset[int]


def _cents(value: Decimal) -> int:
    return int((value * 100).to_integral_value())


async def scope_facts(tenant: TenantContext, snapshot_ids: list[UUID]) -> ScopeFacts:
    async with tenant_session(tenant) as session:
        lines = await lines_of_snapshots(session, snapshot_ids)
        totals = await totals_of_snapshots(session, snapshot_ids)
    amounts = {_cents(v) for line in lines for v in (line.debit, line.credit) if v}
    amounts |= {_cents(v) for pair in totals for v in pair if v}
    return ScopeFacts(
        frozenset(line.account_code for line in lines),
        frozenset(line.account_name for line in lines),
        frozenset(amounts),
    )


async def firm_accounts(tenant: TenantContext) -> list[tuple[str, str]]:
    """Every account code and name in the firm's ledger snapshots."""
    async with tenant_session(tenant) as session:
        return list(await accounts_in_firm(session))


# --- A-02-T22: the `ledger_line` citable's reads (evidence verifies; ledger stays dependency-free)


@dataclass(frozen=True)
class CitedLine:
    """One snapshot line as a `ledger_line` citation reads it, with its snapshot's entity so the
    verifier can hold it to the anchor's engagement."""

    snapshot_id: UUID
    client_entity_id: UUID
    period_end: date
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


async def snapshot_line(
    session: AsyncSession, snapshot_id: UUID, account_code: str
) -> tuple[UUID, CitedLine | None] | None:
    """The snapshot's entity and the named line (None when the snapshot has no such account),
    read in the caller's session (a verifier's unit of work, a reader's session). None when the
    snapshot is not visible here. The caller authorised on an engagement first and must compare
    the entity to that engagement's."""
    snapshot = await get_snapshot(session, snapshot_id)
    if snapshot is None:
        return None
    line = await line_of(session, snapshot_id, account_code)
    if line is None:
        return snapshot.client_entity_id, None
    return snapshot.client_entity_id, CitedLine(
        snapshot.id,
        snapshot.client_entity_id,
        snapshot.period_end,
        line.account_code,
        line.account_name,
        line.debit,
        line.credit,
    )
