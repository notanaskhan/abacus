"""EBP-05: distributions and participant loans (A-05-T42; A-05 F7; DEC-2306).

Reads the adopted loan records (0667) and answers through `compute.ebp.loans`. The figures foot and
tie by code; a person adopts and signs off through P-04's routes. The distributions test is A-03's
second sample set on the shared attribute grid (`variant = ebp_distribution`). An offset reads as a
distribution on line 2e(1) everywhere. The routes have authorised the action and the flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.assurance.compute.ebp import loans as engine

_ZERO: Final = Decimal(0)


@dataclass(frozen=True)
class LoanRow:
    id: UUID
    participant_key: str
    loan_ref: str
    status: str
    originated_on: date | None
    term_months: int | None
    is_residence: bool
    vested_balance: Decimal | None
    loan: engine.Loan
    limit: engine.LoanLimit | None


@dataclass(frozen=True)
class OffsetRow:
    loan_ref: str
    offset_on: date
    amount: Decimal
    form_1099r_code: str | None
    reported_line: str


@dataclass(frozen=True)
class LoansView:
    rows: tuple[LoanRow, ...]
    rollforward: engine.Rollforward
    offsets: tuple[OffsetRow, ...]
    offsets_total: Decimal
    comparative: engine.Comparative
    part_iv_4b: str


def _row(r: object) -> LoanRow:
    m = dict(r)  # type: ignore[call-overload]
    loan = engine.Loan(
        m["loan_ref"], m["beginning_balance"], m["new_loans"], m["repayments"], m["offsets"],
        m["ending_balance"],
    )  # fmt: skip
    limit = None
    if loan.new > 0 and m["vested_balance"] is not None and m["term_months"] is not None:
        limit = engine.loan_limit(
            loan.new, m["vested_balance"], m["term_months"], m["is_residence"]
        )
    return LoanRow(
        m["id"], m["participant_key"], m["loan_ref"], m["status"], m["originated_on"],
        m["term_months"], m["is_residence"], m["vested_balance"], loan, limit,
    )  # fmt: skip


_LOANS = text(
    "SELECT id, participant_key, loan_ref, status, originated_on, term_months, is_residence, "
    "vested_balance, beginning_balance, new_loans, repayments, offsets, ending_balance "
    "FROM ebp_participant_loans WHERE work_item_id = :w ORDER BY loan_ref"
)
_OFFSETS = text(
    "SELECT l.loan_ref, o.offset_on, o.amount, o.form_1099r_code, o.reported_line "
    "FROM ebp_loan_offsets o JOIN ebp_participant_loans l ON l.tenant_id = o.tenant_id "
    "AND l.id = o.loan_id WHERE o.work_item_id = :w ORDER BY o.offset_on, l.loan_ref"
)


async def loans(
    tenant: TenantContext, work_item_id: UUID, py_audited: Decimal | None
) -> LoansView:
    """The rollforward, offsets and PY comparative. `py_audited` is the prior year's audited
    notes receivable from the trust report's beginning column or the PY FS."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_LOANS, {"w": work_item_id})).mappings().all()
        offsets = (await session.execute(_OFFSETS, {"w": work_item_id})).mappings().all()
    found = tuple(_row(r) for r in rows)
    rolled = engine.rollforward([r.loan for r in found])
    offset_rows = tuple(
        OffsetRow(o["loan_ref"], o["offset_on"], o["amount"], o["form_1099r_code"],
                  o["reported_line"])
        for o in offsets
    )  # fmt: skip
    return LoansView(
        found,
        rolled,
        offset_rows,
        engine.offsets_total([o.amount for o in offset_rows]),
        engine.py_comparative(rolled.beginning, py_audited),
        engine.part_iv_4b(),
    )


async def participant_loan(
    tenant: TenantContext, work_item_id: UUID, participant_key: str
) -> tuple[LoanRow, ...]:
    """The EBP-05 drawer: this participant's loans (the note and amortization are the citations)."""
    view = await loans(tenant, work_item_id, None)
    found = tuple(r for r in view.rows if r.participant_key == participant_key)
    if not found:
        raise NotFound("ebp_participant_loan")
    return found


async def py_notes_receivable(tenant: TenantContext, work_item_id: UUID) -> Decimal | None:
    """The trust report's beginning-of-year notes receivable, the comparative's default."""
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text(
                "SELECT boy FROM ebp_trust_report_lines WHERE work_item_id = :w "
                "AND fair_value_level = 'not_certified' AND superseded_by IS NULL "
                "ORDER BY line_key LIMIT 1"
            ),
            {"w": work_item_id},
        )
