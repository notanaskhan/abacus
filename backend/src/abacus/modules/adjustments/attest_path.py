"""The attest CAS path (C-02-T32; TASK-8907; C-02 F4 US-4.1; ADR P-13 / ADR-142, ADR P-16;
DEC-63, DEC-69; red).

An attest-flagged client's close entries are never posted: every one is Review required
(`classify_entry` with `attest_client`, K-02's C21), the batch-within-policy route refuses them,
and the posting path refuses them at the registry (`capabilities.policy_refusal`), the switches
(`w1_switches`) and the batch (`posting.start_batch`), each answering
`attest_client_posting_refused`. What remains is the client's own path (CLS-07 g):

1. **Send to client for approval** (`send_to_approver`): A-06's approve-and-send (C18 kind
   `proposed_entry`, POR-08 e) to the client's **approver of record** (DEC-63), whom the server
   resolves from the engagement's contact designations. A named recipient on an attest close must
   be that person (409 `not_approver_of_record`); no approver of record answers 409
   `approver_of_record_missing`.
2. **Client approved**: the client decides in POR-08 (R-02's applier, `client_approvals`), and the
   entry reads Client approved.
3. **Recorded by the client**: the client records its own entry in its ledger. A person records
   that here, with evidence or a **sync match** that code verifies (`ledger_matches`): a journal in
   the client's ledger for the entry's month or the next whose lines carry every account of the
   entry for the same amount, named by its ledger transaction id (`qbo:<txn id>`). An attest entry
   is recorded only once the client approved it (409 `client_approval_required`), and a match
   reference code cannot find refuses (409 `ledger_match_not_found`).

Nothing here writes to a client's ledger (ADR-040); the client records its own entry.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

APPROVER: Final = "approver_of_record"
MATCH_PREFIX: Final = "qbo:"


class NotApproverOfRecord(DomainConflict):
    """An attest client's entries go to its approver of record only (DEC-63)."""

    code = "not_approver_of_record"


class ApproverOfRecordMissing(DomainConflict):
    """The client has no approver of record on this engagement: name one in its contacts first."""

    code = "approver_of_record_missing"


class ClientApprovalRequired(DomainConflict):
    """An attest client's entry is recorded only after the client approved it in the portal."""

    code = "client_approval_required"


class LedgerMatchNotFound(DomainConflict):
    """No journal in the client's ledger carries this entry's accounts and amounts under that
    reference."""

    code = "ledger_match_not_found"


async def approver_of_record(ctx: AuthContext, engagement_id: UUID) -> UUID:
    from abacus.modules.engagements.api import engagement_contacts

    found = next(
        (
            c.contact_id
            for c in await engagement_contacts(ctx, engagement_id)
            if c.designation == APPROVER
        ),
        None,
    )
    if found is None:
        raise ApproverOfRecordMissing(facts={"engagement_id": str(engagement_id)})
    return found


async def recipient_for(
    ctx: AuthContext, work_item_id: UUID, named: UUID | None
) -> tuple[UUID, bool]:
    """The send's recipient and whether the client is attest. An attest client's entries go to
    its approver of record (named or not); any other send keeps the named contact (A-06)."""
    from abacus.modules.adjustments.entries import engagement_of
    from abacus.modules.engagements.api import attest_of

    engagement_id = await engagement_of(ctx.tenant, work_item_id)
    attest = await attest_of(ctx.tenant, engagement_id) is not False  # unknown reads attest
    if not attest:
        if named is None:
            raise ApproverOfRecordMissing(facts={"reason": "recipient_required"})
        return named, False
    approver = await approver_of_record(ctx, engagement_id)
    if named is not None and named != approver:
        raise NotApproverOfRecord(facts={"contact_id": str(named)})
    return approver, True


# --- the sync match ------------------------------------------------------------------------------


@dataclass(frozen=True)
class EntryLine:
    account_code: str
    amount: Decimal  # absolute: the register shows amounts in the account's natural sign


@dataclass(frozen=True)
class RegisterHit:
    txn_id: str
    account_code: str
    amount: Decimal


def matching_txns(lines: Sequence[EntryLine], hits: Sequence[RegisterHit]) -> list[str]:
    """Pure: the ledger transactions that carry every account of the entry for the same amount
    (each entry line matched by one register line of that transaction), in id order."""
    by_txn: dict[str, list[RegisterHit]] = defaultdict(list)
    for h in hits:
        by_txn[h.txn_id].append(h)
    wanted = sorted((ln.account_code, ln.amount) for ln in lines)
    out: list[str] = []
    for txn, found in by_txn.items():
        pool = sorted((h.account_code, abs(h.amount)) for h in found)
        remaining = list(pool)
        ok = True
        for want in wanted:
            if want in remaining:
                remaining.remove(want)
            else:
                ok = False
                break
        if ok:
            out.append(txn)
    return sorted(out)


def _periods(txn_date: date) -> tuple[str, str]:
    first = f"{txn_date.year:04d}-{txn_date.month:02d}"
    nxt = (txn_date.year + 1, 1) if txn_date.month == 12 else (txn_date.year, txn_date.month + 1)
    year, month = nxt
    return first, f"{year:04d}-{month:02d}"


_ENTRY: Final = text(
    "SELECT e.id, e.engagement_id, e.work_item_id, e.txn_date, e.status, e.is_attest_client, "
    "l.account_code, l.debit, l.credit FROM proposed_entries e JOIN proposed_entry_lines l "
    "ON l.entry_id = e.id WHERE e.id = :id ORDER BY l.line_no"
)


async def _register(
    tenant: TenantContext, client_entity_id: UUID, account: str, period: str
) -> list[RegisterHit]:
    from abacus.modules.ledger.api import PeriodNotAvailable, register_lines

    hits: list[RegisterHit] = []
    cursor: str | None = None
    while True:
        try:
            page, cursor = await register_lines(
                tenant, client_entity_id, account, period, cursor=cursor
            )
        except PeriodNotAvailable:
            return hits
        hits.extend(
            RegisterHit(r.external_txn_id, account, abs(Decimal(r.amount)))
            for r in page
            if r.external_txn_id
        )
        if cursor is None:
            return hits


async def ledger_matches(ctx: AuthContext, entry_id: UUID) -> list[str]:
    """The match references code finds for the entry in the client's synced ledger (the entry's
    month and the next), for a caller that authorised on the entry's engagement."""
    from abacus.modules.engagements.api import get_ref

    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ENTRY, {"id": entry_id})).all()
    if not rows:
        raise NotFound("proposed_entry")
    ref = await get_ref(ctx, rows[0].engagement_id)
    try:
        await authorise(ctx, "proposed_entry.record_external", ref.resource())
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("proposed_entry") from None
        raise
    if rows[0].txn_date is None:
        return []
    lines = [
        EntryLine(
            str(r.account_code),
            Decimal(r.debit) if Decimal(r.debit) > 0 else Decimal(r.credit),
        )
        for r in rows
    ]
    hits: list[RegisterHit] = []
    for period in _periods(rows[0].txn_date):
        for account in sorted({ln.account_code for ln in lines}):
            hits.extend(await _register(ctx.tenant, ref.client_entity_id, account, period))
    return [f"{MATCH_PREFIX}{t}" for t in matching_txns(lines, hits)]


async def check_record(ctx: AuthContext, entry_id: UUID, *, match_ref: str | None) -> None:
    """Before an entry is recorded as in the client's ledger: an attest client's entry must be
    client approved, and a sync match must be one code finds."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT status, is_attest_client FROM proposed_entries WHERE id = :id"),
                {"id": entry_id},
            )
        ).first()
    if row is None:
        raise NotFound("proposed_entry")
    if row.is_attest_client and row.status != "client_approved":
        raise ClientApprovalRequired(facts={"status": str(row.status)})
    if match_ref and match_ref not in await ledger_matches(ctx, entry_id):
        raise LedgerMatchNotFound(facts={"entry_id": str(entry_id)})


def recorded_label(is_attest_client: bool, client_name: str) -> str:
    """CLS-07's row word once recorded (DF-19): an attest client records its own entry."""
    return f"Recorded by {client_name}" if is_attest_client else "Recorded in ledger"


__all__ = [
    "ApproverOfRecordMissing",
    "ClientApprovalRequired",
    "LedgerMatchNotFound",
    "NotApproverOfRecord",
    "approver_of_record",
    "check_record",
    "ledger_matches",
    "matching_txns",
    "recipient_for",
    "recorded_label",
]
