"""Tax workbook v1, the entity returns contract stub (T-05-T06; T-05 §4.3; SPEC-651;
`docs/contracts/tax-workbook.md`). Screens TXP-00, 01, 02, 05, 06, 07, 10, 11.

Every route answers, in order: a client principal 404; `tax.entity_workspace` off for the firm
404 (dark until the flip); its one matrix action (T-05-T04's rows; agent deny on every human verb);
then 501 until its build task. Fixture mode serves the screens from the seed meanwhile.

Classification: every workbook value, memo text and K-1 or partner payload is tax return
information (Restricted, `tri`); a partner's TIN is never in a response (masked last four only;
the reveal is P-12's logged path). Writes carry `Idempotency-Key` and an `expected_version`.
The human verbs here (edit, import, run start, ownership, structure draft, memo draft and edit)
are a person's; sign-offs, proposal approvals and decisions stay P-04's routes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Final, Literal, NoReturn, cast, get_args
from uuid import UUID

from fastapi import Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ENTITY_WORKSPACE
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainTooLarge, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    current_context,
    mask_tins_for,
)

if TYPE_CHECKING:
    from abacus.modules.tax.allocation_structure import Draft

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Tri = classified("restricted", tri=True)
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]

CellAuthor = Literal["run_step", "engine_import", "person", "formula"]
CellState = Literal["value", "formula", "locked_by_run", "stale", "flagged"]
RunScope = Literal["all", "group", "task"]
TallyState = Literal["tie", "off", "check", "pending", "ties_once_posted", "reconciled"]
MemoStatus = Literal["drafting", "adopted", "approved", "stale"]
StructureStatus = Literal["editing", "pending_approval", "approved", "superseded"]
StructureKind = Literal["straight_percentage", "targeted_waterfall"]
ImportKind = Literal["depreciation_register", "state_apportionment"]
WorkbookAction = Literal[
    "workbook.edit",
    "workbook.export",
    "workbook_import.create",
    "workbook_run.start",
    "tax_ownership.edit",
    "allocation_structure.edit",
    "tax_memo.edit",
    "tax_memo.draft",
]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- the rail and the partners -------------------------------------------------------------------


class WorkbookGeneralInformationOut(BaseModel):
    model_config = _cfg()

    return_id: Annotated[UUID, Internal]
    entity_name: Annotated[str, Confidential]
    form: Annotated[Literal["1065", "1120-S", "1120", "990"], Internal]
    tax_year: Annotated[int, Internal]
    ein_last4: Annotated[
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None
    accounting_method: Annotated[str | None, Internal] = None
    preparer_name: Annotated[str | None, Confidential] = None
    reviewer_name: Annotated[str | None, Confidential] = None
    signer_name: Annotated[str | None, Confidential] = None


class WorkbookPartnerOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    name: Annotated[str, Tri]
    tin_last4: Annotated[  # never the full TIN
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None
    kind: Annotated[Literal["general", "limited", "llc_member"], Internal]


class WorkbookOwnershipPeriodOut(BaseModel):
    model_config = _cfg()

    starts_on: Annotated[date, Internal]
    ends_on: Annotated[date, Internal]
    shares: Annotated[dict[str, Decimal], Tri]  # partner id → percentage (exact decimal)


class WorkbookInterestTransferOut(BaseModel):
    model_config = _cfg()

    on: Annotated[date, Internal]
    from_partner_id: Annotated[UUID, Internal]
    to_partner_id: Annotated[UUID, Internal]
    percentage: Annotated[Decimal, Tri]
    citation_id: Annotated[UUID | None, Internal] = None


class WorkbookPartnersOut(BaseModel):
    model_config = _cfg()

    version: Annotated[int, Internal]
    partners: Annotated[list[WorkbookPartnerOut], Tri]
    periods: Annotated[list[WorkbookOwnershipPeriodOut], Tri]
    transfers: Annotated[list[WorkbookInterestTransferOut], Tri]
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class WorkbookOwnershipIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    periods: Annotated[list[WorkbookOwnershipPeriodOut], Field(min_length=1, max_length=24), Tri]
    transfers: Annotated[list[WorkbookInterestTransferOut], Field(max_length=50), Tri] = Field(
        default_factory=list[WorkbookInterestTransferOut]
    )
    citation_note: Annotated[str, Field(min_length=1, max_length=500), Tri]


# --- the workbook ------------------------------------------------------------------------------


class WorkbookSheetOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]  # "05_capital"
    title: Annotated[str, Internal]
    flagged: Annotated[int, Field(ge=0), Internal] = 0
    imported_from: Annotated[str | None, Internal] = None  # an import-mode sheet's source


class WorkbookVersionOut(BaseModel):
    """T-05-T38 rest (DEC-4630): a version of the workbook is the state a finished run left."""

    model_config = _cfg()

    version: Annotated[int, Internal]  # = the run's number ("Version 2 · Run 2")
    run_no: Annotated[int, Internal]
    finished_at: Annotated[datetime, Internal]


class WorkbookOut(BaseModel):
    model_config = _cfg()

    return_id: Annotated[UUID, Internal]
    version: Annotated[int, Internal]
    sheets: Annotated[list[WorkbookSheetOut], Internal]
    allowed_actions: Annotated[list[WorkbookAction], Internal]
    # T-05-T38 rest (DEC-4630), additive: the finished runs' versions, newest first; `version`
    # is the newest (the live workbook, with any edits since), 1 before the first run finishes.
    versions: Annotated[list[WorkbookVersionOut], Internal] = Field(
        default_factory=list[WorkbookVersionOut]
    )


class WorkbookCellOut(BaseModel):
    model_config = _cfg()

    address: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[0-9]{1,6}$"), Internal]
    value: Annotated[str | None, Tri] = None  # exact decimal or text, as stored
    formula: Annotated[str | None, Tri] = None  # E13's closed grammar (ADR-237)
    author: Annotated[CellAuthor, Internal]
    state: Annotated[CellState, Internal]
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    version: Annotated[int, Internal]
    # T-05-T35 (DEC-4620): an edit's dependents recomputed, and a reviewer's proposal note
    recomputed: Annotated[list[str], Internal] = Field(default_factory=list[str])
    proposal_note_id: Annotated[UUID | None, Internal] = None
    checkpoint_id: Annotated[UUID | None, Internal] = None


class WorkbookSheetCellsOut(BaseModel):
    model_config = _cfg()

    sheet: Annotated[str, Internal]
    version: Annotated[int, Internal]
    cells: Annotated[list[WorkbookCellOut], Tri]
    next_range: Annotated[str | None, Internal] = None


class WorkbookCellProvenanceOut(BaseModel):
    model_config = _cfg()

    cell: Annotated[WorkbookCellOut, Tri]
    writer: Annotated[str, Confidential]  # "Run 3 · started by Samuel Ito", "Olivia Brandt"
    inputs: Annotated[list[str], Internal] = Field(default_factory=list[str])
    issue_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class WorkbookCellEditIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    value: Annotated[str | None, Field(max_length=200), Tri] = None
    formula: Annotated[str | None, Field(max_length=2000), Tri] = None


class WorkbookImportAcceptedOut(BaseModel):
    model_config = _cfg()

    import_id: Annotated[UUID, Internal]
    kind: Annotated[ImportKind, Internal]
    cells: Annotated[int, Field(ge=0), Internal]


class WorkbookRunIn(BaseModel):
    model_config = _cfg()

    scope: Annotated[RunScope, Internal]
    keys: Annotated[list[str], Field(max_length=50), Internal] = Field(default_factory=list[str])


class WorkbookRunAcceptedOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    run_no: Annotated[int, Internal]


class WorkbookRunRowOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    run_no: Annotated[int, Internal]
    started_by: Annotated[str, Confidential]
    started_at: Annotated[datetime, Internal]
    state: Annotated[str, Internal]  # agent_run (C2)


class WorkbookRunsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookRunRowOut], Internal]


# --- TB → TTB, tallies, entries, mapping --------------------------------------------------------


class WorkbookTbRowOut(BaseModel):
    model_config = _cfg()

    account_code: Annotated[str, Confidential]
    account_name: Annotated[str, Confidential]
    form_line_key: Annotated[str | None, Internal] = None
    unadjusted: Annotated[Decimal, Tri]
    aje: Annotated[Decimal, Tri]
    rje: Annotated[Decimal, Tri]
    tje: Annotated[Decimal, Tri]
    tax_basis: Annotated[Decimal, Tri]
    # T-05-T37 (DEC-4622), additive: ATB, the prior year's TB once imported, and the section
    adjusted: Annotated[MaybeMoney, Tri] = None
    prior_year: Annotated[MaybeMoney, Tri] = None
    group: Annotated[
        Literal["assets", "liabilities", "equity", "income", "deductions", "unmapped"] | None,
        Internal,
    ] = None
    # T-05-T37 rest (DEC-4629), additive: the row's sheet 01 cells by column (`utb`, `aje`,
    # `rje`, `atb` → "01!C5"), SHL-09's address; empty by form line or before the import.
    cells: Annotated[dict[str, str], Internal] = Field(default_factory=dict[str, str])


class WorkbookTbTotalOut(BaseModel):
    """T-05-T37: a section's totals or the TB total, computed by the server."""

    model_config = _cfg()

    key: Annotated[str, Internal]  # "assets" … "deductions", "tb_total"
    label: Annotated[str, Internal]
    unadjusted: Annotated[Decimal, Tri]
    aje: Annotated[Decimal, Tri]
    rje: Annotated[Decimal, Tri]
    adjusted: Annotated[Decimal, Tri]
    tje: Annotated[Decimal, Tri]
    tax_basis: Annotated[Decimal, Tri]
    prior_year: Annotated[MaybeMoney, Tri] = None


class WorkbookTrialBalanceOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["account", "line"], Internal]
    rows: Annotated[list[WorkbookTbRowOut], Tri]
    unmapped: Annotated[int, Field(ge=0), Internal]
    totals: Annotated[list[WorkbookTbTotalOut], Tri] = Field(
        default_factory=list[WorkbookTbTotalOut]
    )


class WorkbookTermOut(BaseModel):
    """T-05-T37 rest (DEC-4629): one term of a card's derivation, added or taken away."""

    model_config = _cfg()

    label: Annotated[str, Confidential]  # an account's name or a fixed label
    amount: Annotated[Decimal, Tri]
    op: Annotated[Literal["+", "-"], Internal] = "+"


class WorkbookTallyOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    state: Annotated[TallyState, Internal]
    difference: Annotated[MaybeMoney, Tri] = None
    terms: Annotated[list[WorkbookTermOut], Tri] = Field(default_factory=list[WorkbookTermOut])


class WorkbookFigureOut(BaseModel):
    """T-05-T37: a figure card's amount (gross rents, total deductions, …), the server's."""

    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    amount: Annotated[Decimal, Tri]
    terms: Annotated[list[WorkbookTermOut], Tri] = Field(default_factory=list[WorkbookTermOut])


class WorkbookTalliesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookTallyOut], Tri]
    figures: Annotated[list[WorkbookFigureOut], Tri] = Field(
        default_factory=list[WorkbookFigureOut]
    )


class WorkbookJournalEntryLineOut(BaseModel):
    """T-05-T37 rest (DEC-4629): one line of an entry, for TXP-02's drawer (O2)."""

    model_config = _cfg()

    account_code: Annotated[str, Confidential]
    account_name: Annotated[str | None, Confidential] = None
    debit: Annotated[Decimal, Tri]
    credit: Annotated[Decimal, Tri]


class WorkbookJournalEntryOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    kind: Annotated[Literal["aje", "rje", "tje"], Internal]
    reference: Annotated[str, Internal]  # "TJE-3"
    amount: Annotated[Decimal, Tri]
    state: Annotated[str, Internal]
    # T-05-T37 rest (DEC-4629), additive: the drawer's memo, lines and the named approval.
    description: Annotated[str | None, Confidential] = None
    lines: Annotated[list[WorkbookJournalEntryLineOut], Tri] = Field(
        default_factory=list[WorkbookJournalEntryLineOut]
    )
    approval: Annotated[str | None, Internal] = None  # "Approved by Samuel Ito under …"


class WorkbookJournalEntriesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookJournalEntryOut], Tri]


class WorkbookFormLineOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]


class WorkbookFormLinesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookFormLineOut], Internal]


class WorkbookMappingIn(BaseModel):
    model_config = _cfg()

    account_code: Annotated[str, Field(min_length=1, max_length=40), Confidential]
    form_line_key: Annotated[str, Field(min_length=1, max_length=80), Internal]
    rationale: Annotated[str | None, Field(max_length=500), Confidential] = None


class WorkbookMappingProposedOut(BaseModel):
    """DEC-4629: the tax reviewer's pick maps the account (`mapped`); anyone else's pick is a
    review note proposing the line to the reviewer (`flagged`, `note_id`), and nothing maps.
    `proposal_id` stays because v1 is frozen (DEC-4824): the record the pick wrote, the review
    note when flagged, the mapping set when mapped."""

    model_config = _cfg()

    proposal_id: Annotated[UUID, Internal]
    state: Annotated[Literal["mapped", "flagged"], Internal]
    account_code: Annotated[str, Confidential]
    form_line_key: Annotated[str, Internal]
    note_id: Annotated[UUID | None, Internal] = None


# --- Schedule K, capital, M-2 ------------------------------------------------------------------


class WorkbookScheduleKCellOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    amount: Annotated[Decimal, Tri]


class WorkbookScheduleKLineOut(BaseModel):
    model_config = _cfg()

    line: Annotated[str, Internal]  # "1", "2", "13d"
    label: Annotated[str, Internal]
    total: Annotated[Decimal, Tri]
    by_partner: Annotated[list[WorkbookScheduleKCellOut], Tri]
    tie: Annotated[TallyState, Internal]


class WorkbookScheduleKOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["federal", "state"], Internal]
    lines: Annotated[list[WorkbookScheduleKLineOut], Tri]
    # T-05-T43 (DEC-4707), additive: Analysis of Net Income line 1 (federal view only).
    analysis: Annotated[WorkbookScheduleKLineOut | None, Tri] = None


class WorkbookBreakdownRowOut(BaseModel):
    model_config = _cfg()

    property_name: Annotated[str, Confidential]
    amount: Annotated[Decimal, Tri]


class WorkbookBreakdownOut(BaseModel):
    model_config = _cfg()

    line: Annotated[str, Internal]
    rows: Annotated[list[WorkbookBreakdownRowOut], Tri]


class WorkbookCapitalRowOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    beginning: Annotated[Decimal, Tri]
    contributions: Annotated[Decimal, Tri]
    income: Annotated[Decimal, Tri]
    distributions: Annotated[Decimal, Tri]
    ending: Annotated[Decimal, Tri]
    name: Annotated[str | None, Confidential] = None  # T-05-T34: the 05 row's partner name
    # T-05-T55 (DEC-4911), additive: 05's columns G-L (None where blank: TXP-07 draws "—").
    tax_exempt: Annotated[Decimal | None, Tri] = None
    tax_exempt_704b: Annotated[Decimal | None, Tri] = None
    nondeductible: Annotated[Decimal | None, Tri] = None
    transfers: Annotated[Decimal | None, Tri] = None
    guaranteed_payments: Annotated[Decimal | None, Tri] = None
    ending_704b: Annotated[Decimal | None, Tri] = None
    # The 05 row's number, for SHL-09 (`05!G<row>`).
    row: Annotated[int | None, Internal] = None


class WorkbookCapitalTotalsOut(BaseModel):
    """T-05-T34: the server's column totals (the screen never sums)."""

    model_config = _cfg()

    beginning: Annotated[Decimal, Tri]
    contributions: Annotated[Decimal, Tri]
    income: Annotated[Decimal, Tri]
    distributions: Annotated[Decimal, Tri]
    ending: Annotated[Decimal, Tri]
    # T-05-T55 (DEC-4911), additive: Σ tax-exempt income on the tax basis ("OTHER INCREASES")
    # and Σ transfers (nets to 0).
    tax_exempt: Annotated[Decimal | None, Tri] = None
    transfers: Annotated[Decimal | None, Tri] = None
    ending_704b: Annotated[Decimal | None, Tri] = None


class WorkbookItemLOut(BaseModel):
    """T-05-T34: Item L's ending capital (the partners') against the M-2's line 9."""

    model_config = _cfg()

    capital_ending: Annotated[Decimal, Tri]
    m2_ending: Annotated[Decimal, Tri]
    tie: Annotated[TallyState, Internal]
    difference: Annotated[Decimal, Tri]


class WorkbookCapitalAccountsOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["by_partner", "by_movement"], Internal]
    basis: Annotated[Literal["tax", "gaap", "section_704b"], Internal]
    rows: Annotated[list[WorkbookCapitalRowOut], Tri]
    tie: Annotated[TallyState, Internal]
    totals: Annotated[WorkbookCapitalTotalsOut | None, Tri] = None
    item_l: Annotated[WorkbookItemLOut | None, Tri] = None
    # T-05-T55 (DEC-4911), additive: the §704(b)/book endings against Schedule L, and Item L
    # derived from the rows (Σ endings = the total).
    book_tie: Annotated[TallyState, Internal] = "pending"
    derives_tie: Annotated[TallyState, Internal] = "pending"


class WorkbookM2LineOut(BaseModel):
    model_config = _cfg()

    line: Annotated[int, Internal]
    label: Annotated[str, Internal]
    amount: Annotated[Decimal, Tri]


class WorkbookM2Out(BaseModel):
    model_config = _cfg()

    variant: Annotated[Literal["as_drafted", "with_fix"], Internal]
    beginning: Annotated[Decimal, Tri]
    ending: Annotated[Decimal, Tri]
    tie: Annotated[TallyState, Internal]
    difference: Annotated[MaybeMoney, Tri] = None
    lines: Annotated[list[WorkbookM2LineOut], Tri] = Field(default_factory=list[WorkbookM2LineOut])
    item_l: Annotated[WorkbookItemLOut | None, Tri] = None


# --- the allocation structure ------------------------------------------------------------------


class WorkbookRungOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    amount: Annotated[MaybeMoney, Tri] = None
    percentage: Annotated[Decimal | None, Tri] = None
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class WorkbookAllocationPeriodOut(BaseModel):
    """T-05-T41: one period (straight percentage) or one rung's total (waterfall)."""

    model_config = _cfg()

    key: Annotated[str, Internal]
    starts_on: Annotated[date | None, Internal] = None
    ends_on: Annotated[date | None, Internal] = None
    amount: Annotated[Decimal, Tri]
    # T-05-T44 (DEC-4710): a waterfall rung's prior tiers, what was available to it and what is
    # left after it (server's arithmetic; the screen draws).
    prior: Annotated[MaybeMoney, Tri] = None
    available: Annotated[MaybeMoney, Tri] = None
    remaining: Annotated[MaybeMoney, Tri] = None


class WorkbookAllocationResultOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    period_key: Annotated[str, Internal]
    rung_priority: Annotated[int | None, Internal] = None
    amount: Annotated[Decimal, Tri]


class WorkbookAllocationPartnerOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    name: Annotated[str, Tri]
    kind: Annotated[Literal["gp", "lp", "member", "shareholder"], Internal]
    total: Annotated[Decimal, Tri]
    # T-05-T44: the back-solve (waterfall): beginning 704(b) capital and the target (+ the plug).
    beginning: Annotated[MaybeMoney, Tri] = None
    target: Annotated[MaybeMoney, Tri] = None


class WorkbookAllocationStructureOut(BaseModel):
    model_config = _cfg()

    version: Annotated[int, Internal]
    kind: Annotated[StructureKind, Internal]
    status: Annotated[StructureStatus, Internal]
    rungs: Annotated[list[WorkbookRungOut], Tri]
    seen_hash: Annotated[str, Internal]  # what an L3 sign-off names (P-04)
    allowed_actions: Annotated[list[WorkbookAction], Internal]
    # T-05-T41 (DEC-4701), additive: what TXP-06 draws and the target its L3 names.
    structure_id: Annotated[UUID | None, Internal] = None
    sign_off_target_id: Annotated[UUID | None, Internal] = None
    latest_version: Annotated[int, Internal] = 0
    method: Annotated[Literal["interim_closing", "proration"], Internal] = "interim_closing"
    convention: Annotated[Literal["calendar_day", "semi_monthly", "monthly"], Internal] = (
        "calendar_day"
    )
    proposed_by: Annotated[Literal["human", "agent"] | None, Internal] = None
    income: Annotated[MaybeMoney, Tri] = None
    distributable: Annotated[MaybeMoney, Tri] = None
    periods: Annotated[list[WorkbookAllocationPeriodOut], Tri] = Field(
        default_factory=list[WorkbookAllocationPeriodOut]
    )
    partners: Annotated[list[WorkbookAllocationPartnerOut], Tri] = Field(
        default_factory=list[WorkbookAllocationPartnerOut]
    )
    results: Annotated[list[WorkbookAllocationResultOut], Tri] = Field(
        default_factory=list[WorkbookAllocationResultOut]
    )
    checks: Annotated[dict[str, bool], Internal] = Field(default_factory=dict[str, bool])
    gp_profit_percent: Annotated[Decimal | None, Tri] = None
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    persisted: Annotated[bool, Internal] = True  # False on a preview


class WorkbookAllocationDraftIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    kind: Annotated[StructureKind, Internal]
    rungs: Annotated[list[WorkbookRungOut], Field(min_length=1, max_length=20), Tri]
    # T-05-T41, additive: the §706(d) method and convention, the year's income (the waterfall's
    # and proration's) and the closed-books amounts by segment (interim closing; else 04's).
    method: Annotated[Literal["interim_closing", "proration"], Internal] = "interim_closing"
    convention: Annotated[Literal["calendar_day", "semi_monthly", "monthly"], Internal] = (
        "calendar_day"
    )
    income: Annotated[MaybeMoney, Tri] = None
    segment_amounts: Annotated[list[Money], Field(max_length=24), Tri] = Field(
        default_factory=list[Decimal]
    )


class WorkbookAllocationApproveIn(BaseModel):
    """T-05-T41: TXP-06 c2's "Approve structure" (SHL-12 at L3)."""

    model_config = _cfg()

    seen_hash: Annotated[str, Field(min_length=64, max_length=71), Internal]
    statement_version: Annotated[str, Field(min_length=1, max_length=40), Internal]


class WorkbookAllocationApprovedOut(BaseModel):
    model_config = _cfg()

    sign_off_id: Annotated[UUID, Internal]
    structure_id: Annotated[UUID, Internal]
    run_id: Annotated[UUID | None, Internal] = None  # the capital and K-1 re-run
    run_no: Annotated[int | None, Internal] = None


# --- sections, issues, the memo, reconciliation ------------------------------------------------


class WorkbookSectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Internal]
    tallies: Annotated[list[WorkbookTallyOut], Tri]
    signed_levels: Annotated[list[str], Internal]
    # T-05-T42 (DEC-4705), additive: the sign-off target, what it names and stale levels.
    section_id: Annotated[UUID | None, Internal] = None
    seen_hash: Annotated[str, Internal] = ""
    stale_levels: Annotated[list[str], Internal] = Field(default_factory=list[str])


class WorkbookSectionsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookSectionOut], Tri]


class WorkbookSectionSignOffIn(BaseModel):
    model_config = _cfg()

    level: Annotated[Literal["l1", "l2", "l3"], Internal]  # T-05-T42: L1 is the preparer's
    seen_hash: Annotated[str, Internal]
    note: Annotated[str | None, Field(max_length=500), Confidential] = None
    statement_version: Annotated[str | None, Field(max_length=40), Internal] = None


class WorkbookSignOffRecordedOut(BaseModel):
    model_config = _cfg()

    sign_off_id: Annotated[UUID, Internal]


class WorkbookIssueAssigneeOut(BaseModel):
    """T-05-T51: a person or the Accrued Agent."""

    model_config = _cfg()

    kind: Annotated[Literal["person", "agent"], Internal]
    user_id: Annotated[UUID | None, Internal] = None
    name: Annotated[str, Internal]


class WorkbookIssueCellLinkOut(BaseModel):
    """T-05-T51: a linked cell range, for TXP-11's match lighting."""

    model_config = _cfg()

    sheet: Annotated[str, Internal]
    range: Annotated[str, Internal]


class WorkbookReturnIssueOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    section: Annotated[str | None, Internal] = None
    step: Annotated[str | None, Internal] = None
    status: Annotated[str, Internal]
    # T-05-T51 (DEC-4903), additive: the queue row's facts.
    kind: Annotated[str, Internal] = "review_point"
    priority: Annotated[str, Internal] = "normal"
    source_kind: Annotated[str | None, Internal] = None
    category_path: Annotated[str | None, Internal] = None
    blocks: Annotated[list[str], Internal] = Field(default_factory=list[str])
    assignee: Annotated[WorkbookIssueAssigneeOut | None, Internal] = None
    cells: Annotated[list[WorkbookIssueCellLinkOut], Internal] = Field(
        default_factory=list[WorkbookIssueCellLinkOut]
    )
    request_item_id: Annotated[UUID | None, Internal] = None
    version: Annotated[int, Internal] = 1
    created_at: Annotated[datetime | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = Field(default_factory=list[str])


class WorkbookIssueSectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[Literal["waiting_on_client", "review_points"], Internal]
    title: Annotated[str, Internal]
    count: Annotated[int, Internal]


class WorkbookReturnIssuesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookReturnIssueOut], Confidential]
    by_section: Annotated[dict[str, int], Internal]
    by_step: Annotated[dict[str, int], Internal]
    # T-05-T51, additive: the badge (open total), Show resolved's count and the two headings.
    open_total: Annotated[int, Internal] = 0
    resolved_total: Annotated[int, Internal] = 0
    sections: Annotated[list[WorkbookIssueSectionOut], Internal] = Field(
        default_factory=list[WorkbookIssueSectionOut]
    )


class WorkbookIssueAssigneeOptionOut(BaseModel):
    model_config = _cfg()

    kind: Annotated[Literal["person", "agent", "client_contact"], Internal]
    id: Annotated[UUID | None, Internal] = None
    name: Annotated[str, Confidential]
    detail: Annotated[str | None, Internal] = None


class WorkbookIssueAssigneesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookIssueAssigneeOptionOut], Confidential]


class WorkbookIssueSendIn(BaseModel):
    """T-05-T51: the issue's own client wording goes; the body never carries text."""

    model_config = _cfg()

    seen_version: Annotated[int, Field(ge=1), Internal]
    contact_id: Annotated[UUID, Internal]
    due_on: Annotated[date | None, Internal] = None


class WorkbookIssueSentOut(BaseModel):
    model_config = _cfg()

    request_item_id: Annotated[UUID, Internal]


class WorkbookIssueReminderOut(BaseModel):
    model_config = _cfg()

    drafts: Annotated[int, Internal]


class WorkbookIssueResolvedOut(BaseModel):
    model_config = _cfg()

    issue_id: Annotated[UUID, Internal]
    noted: Annotated[bool, Internal]


class WorkbookIssueResolveIn(BaseModel):
    model_config = _cfg()

    seen_version: Annotated[int, Field(ge=1), Internal]
    note: Annotated[str | None, Field(max_length=1000), Confidential] = None


class WorkbookMemoSectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Internal]
    body: Annotated[str, Tri]
    human_owned: Annotated[bool, Internal]
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    version: Annotated[int, Internal]


class WorkbookMemoOut(BaseModel):
    model_config = _cfg()

    status: Annotated[MemoStatus, Internal]
    sections: Annotated[list[WorkbookMemoSectionOut], Tri]
    seen_hash: Annotated[str, Internal]
    stale_fields: Annotated[list[str], Internal] = Field(default_factory=list[str])
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class WorkbookMemoDraftIn(BaseModel):
    model_config = _cfg()

    sections: Annotated[list[str], Field(max_length=12), Internal] = Field(
        default_factory=list[str]
    )


class WorkbookMemoSectionEditIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    body: Annotated[str, Field(min_length=1, max_length=20_000), Tri]


class WorkbookMemoAdoptIn(BaseModel):
    model_config = _cfg()

    seen_hash: Annotated[str, Internal]


class WorkbookOpportunityOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Confidential]


class WorkbookOpportunitiesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookOpportunityOut], Confidential]


class WorkbookReconciliationRowOut(BaseModel):
    model_config = _cfg()

    field_key: Annotated[str, Internal]
    accrued: Annotated[MaybeMoney, Tri] = None
    engine: Annotated[MaybeMoney, Tri] = None
    issue_id: Annotated[UUID | None, Internal] = None
    # T-05-T61 (additive): the line's words (code's) and whether it needs explaining.
    label: Annotated[str | None, Confidential] = None
    differs: Annotated[bool, Internal] = False


class WorkbookReconciliationOut(BaseModel):
    model_config = _cfg()

    checkpoint_id: Annotated[UUID | None, Internal] = None
    rows: Annotated[list[WorkbookReconciliationRowOut], Tri]
    differences: Annotated[int, Field(ge=0), Internal]
    # T-05-T61 (additive; DEC-77): the words beside Accrued's figures the engine owns.
    accrued_label: Annotated[str, Internal] = "Accrued tie-out (shadow)"


class WorkbookAcceptedOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

workbook_router = AbacusRouter(prefix="/v1", tags=["tax workbook"])
_R = "/tax-returns/{return_id}"


async def _flag_on(ctx: AuthContext) -> None:
    """A client principal never reaches the workspace; the flag off answers 404."""
    if ctx.client or not await flag_enabled(ctx.tenant, TAX_ENTITY_WORKSPACE):
        raise NotFound(TAX_ENTITY_WORKSPACE.name)


async def _workbook_read(ctx: AuthContext, return_id: UUID) -> tuple[str, Resource]:
    """The return as the viewer may see it (404 otherwise) and `workbook.read` on it."""
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, "workbook.read", resource)
    return str(loaded.row.form), resource


async def _authorise_edit(ctx: AuthContext, resource: Resource) -> None:
    """A person's cell edit on the return (never an agent's: ADR-005)."""
    await authorise(ctx, "workbook.edit", resource)


async def _authorise_import(ctx: AuthContext, resource: Resource) -> None:
    """T-05-T40: a person imports a report (never an agent, ADR-005)."""
    await authorise(ctx, "workbook_import.create", resource)


async def _authorise_structure_edit(ctx: AuthContext, resource: Resource) -> None:
    """T-05-T41: a person drafts an allocation structure (never an agent, ADR-005)."""
    await authorise(ctx, "allocation_structure.edit", resource)


async def _authorise_run_start(ctx: AuthContext, resource: Resource) -> None:
    """A person starts the workbook run (never an agent: ADR-005)."""
    await authorise(ctx, "workbook_run.start", resource)


async def _authorise_export(ctx: AuthContext, resource: Resource) -> None:
    """T-05-T57: a person exports the workbook (fresh MFA; never an agent, ADR-005)."""
    await authorise(ctx, "workbook.export", resource)


async def _authorise_memo_draft(ctx: AuthContext, resource: Resource) -> None:
    """T-05-T54: a person starts the memo's run (never an agent, ADR-005)."""
    await authorise(ctx, "tax_memo.draft", resource)


async def _authorise_memo_edit(ctx: AuthContext, resource: Resource) -> None:
    """T-05-T54: a person edits a memo section (never an agent, ADR-005)."""
    await authorise(ctx, "tax_memo.edit", resource)


class PayloadTooLarge(DomainTooLarge):
    """T-05-T40: a workbook import over 5 MB (413)."""

    code = "import_too_large"


class RunInProgress(DomainConflict):
    """A workbook run of this return is still open: one at a time (TXP-00)."""

    code = "run_in_progress"


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@workbook_router.get(
    f"{_R}/general-information", action="tax_return.read",
    response_model=WorkbookGeneralInformationOut,
)  # fmt: skip
async def entity_general_information_route(
    return_id: UUID, ctx: Ctx
) -> WorkbookGeneralInformationOut:
    """The rail's facts (S41 leftovers, DEC-4737): the entity, form and year, the EIN's last four,
    the accounting method and the ladder's preparer, reviewer and signer."""
    from abacus.modules.identity.api import names_of
    from abacus.modules.organisations.api import (
        client_of_entity,
        entity_display_name,
        entity_tin_last4s,
    )
    from abacus.modules.tax.entity_partners import accounting_method, ladder_people
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    await authorise(ctx, "tax_return.read", await return_resource(ctx, loaded))
    entity = loaded.client_entity_id
    client = await client_of_entity(ctx.tenant, entity)
    last4s = sorted(await entity_tin_last4s(ctx.tenant, client, entity)) if client else []
    people = ladder_people(loaded.facts.assignees)
    names = await names_of(sorted({p for p in people if p is not None}, key=str))
    preparer, reviewer, signer = (None if p is None else names.get(p) for p in people)
    # The answer carries the EIN's last four (Restricted, pii_kind tin): masked for an offshore
    # reader (review 6; S35 round 2 end pass).
    return await mask_tins_for(
        ctx,
        WorkbookGeneralInformationOut(
            return_id=return_id,
            entity_name=await entity_display_name(ctx.tenant, entity) or loaded.facts.client_name,
            form=cast(Literal["1065", "1120-S", "1120", "990"], str(loaded.row.form)),
            tax_year=int(loaded.row.tax_year),
            ein_last4=last4s[0] if len(last4s) == 1 else None,
            accounting_method=await accounting_method(ctx.tenant, return_id),
            preparer_name=preparer,
            reviewer_name=reviewer,
            signer_name=signer,
        ),
    )


@workbook_router.get(
    f"{_R}/partners", action="tax_return.read", response_model=WorkbookPartnersOut
)
async def entity_partners_route(return_id: UUID, ctx: Ctx) -> WorkbookPartnersOut:
    """TXP-05's columns and Item J (S41 leftovers, DEC-4737): the partners in order, the ownership
    periods and the interest transfers; `tax_ownership.edit` when the viewer holds it."""
    from abacus.modules.tax.entity_partners import ownership
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, "tax_return.read", resource)
    held = await allowed_actions(ctx, resource, ("tax_ownership.edit",))
    found = await ownership(ctx.tenant, return_id)
    # The answer carries each partner's TIN last four (Restricted, pii_kind tin): masked for an
    # offshore reader (review 6; S35 round 2 end pass).
    return await mask_tins_for(
        ctx,
        WorkbookPartnersOut(
            version=found.version,
            partners=[
                WorkbookPartnerOut(id=p.id, name=p.name, tin_last4=p.tin_last4, kind=p.kind)
                for p in found.partners
            ],
            periods=[
                WorkbookOwnershipPeriodOut(
                    starts_on=p.starts_on, ends_on=p.ends_on, shares=p.shares
                )
                for p in found.periods
            ],
            transfers=[
                WorkbookInterestTransferOut(
                    on=t.on,
                    from_partner_id=t.from_partner_id,
                    to_partner_id=t.to_partner_id,
                    percentage=t.percentage,
                    citation_id=t.citation_id,
                )
                for t in found.transfers
            ],
            allowed_actions=["tax_ownership.edit"] if "tax_ownership.edit" in held else [],
        ),
    )


@workbook_router.put(
    f"{_R}/ownership", action="tax_ownership.edit", response_model=WorkbookPartnersOut,
    errors=(409, 501),
)  # fmt: skip
async def entity_ownership_route(
    return_id: UUID, body: WorkbookOwnershipIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookPartnersOut:
    await _flag_on(ctx)
    # The answer carries EIN and TIN last fours (Restricted, pii_kind tin): masked for an
    # offshore reader once the stub answers (review 6; S35 round 2 end pass).
    return await mask_tins_for(ctx, _not_yet())


@workbook_router.get(
    f"{_R}/workbook", action="workbook.read", response_model=WorkbookOut, errors=(501,)
)
async def workbook_route(return_id: UUID, ctx: Ctx) -> WorkbookOut:
    """TXP-11's sheet tabs (T-05-T27): the form's sheets in order and what the viewer may do."""
    await _flag_on(ctx)
    form, resource = await _workbook_read(ctx, return_id)
    from abacus.modules.tax.workbook_service import sheets_of

    held = await allowed_actions(ctx, resource, get_args(WorkbookAction))
    versions = await _versions(ctx, return_id)
    return WorkbookOut(
        return_id=return_id,
        version=versions[0].version if versions else 1,
        sheets=[WorkbookSheetOut(key=n, title=t) for n, t in sheets_of(form)],
        allowed_actions=[cast(WorkbookAction, a) for a in get_args(WorkbookAction) if a in held],
        versions=versions,
    )


async def _versions(ctx: AuthContext, return_id: UUID) -> list[WorkbookVersionOut]:
    """DEC-4630: each finished run of the return is a version, newest first."""
    from abacus.modules.agents.api import work_item_runs

    runs = await work_item_runs(ctx.tenant, f"tax_return:{return_id}")
    return [
        WorkbookVersionOut(version=r.run_number, run_no=r.run_number, finished_at=r.finished_at)
        for r in sorted(runs, key=lambda r: r.run_number, reverse=True)
        if r.finished_at is not None
    ]


_AUTHOR: Final[dict[str, CellAuthor]] = {
    "formula": "formula",
    "engine_import": "engine_import",
    "tb_linked": "run_step",
    "human": "person",
}


@workbook_router.get(
    f"{_R}/workbook/sheets/{{sheet}}", action="workbook.read",
    response_model=WorkbookSheetCellsOut,
    errors=(501,),
)  # fmt: skip
async def entity_sheet_route(
    return_id: UUID,
    sheet: str,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
    range_: Annotated[str | None, Query(alias="range", max_length=40)] = None,
) -> WorkbookSheetCellsOut:
    """One sheet with range paging (T-05-T27): values and formulas, never evaluated text.

    T-05-T38 rest (DEC-4630): `version` names a finished run; the sheet reads as it stood when
    that run finished (review's insert-only versions at that instant). No version, or the newest,
    is the live workbook with each cell's writer and citations."""
    await _flag_on(ctx)
    form, _resource = await _workbook_read(ctx, return_id)
    from abacus.modules.review.api import (
        current_values,
        latest_citations,
        latest_sources,
        values_as_of,
    )
    from abacus.modules.tax.workbook_service import WORKBOOK, sheet_cells, sheet_or_404

    key = sheet_or_404(form, sheet)
    versions = await _versions(ctx, return_id)
    newest = versions[0].version if versions else 1
    if version is not None and version != newest:
        found = next((v for v in versions if v.version == version), None)
        if found is None:
            raise NotFound("workbook_version")  # no finished run of the return has that number
        then = await values_as_of(ctx.tenant, WORKBOOK, [return_id], found.finished_at)
        cells, next_range = sheet_cells(then.get(return_id, {}), key, range_)
        return WorkbookSheetCellsOut(
            sheet=sheet,
            version=version,
            cells=[
                WorkbookCellOut(
                    address=c.address,
                    value=c.value,
                    formula=c.formula,
                    author="formula" if c.formula else "person",
                    state="formula" if c.formula else "value",
                    version=version,
                )
                for c in cells
            ],
            next_range=next_range,
        )
    values = await current_values(ctx.tenant, WORKBOOK, return_id)
    cells, next_range = sheet_cells(values, key, range_)
    sources = await latest_sources(ctx.tenant, WORKBOOK, [return_id])
    cites = await latest_citations(ctx.tenant, WORKBOOK, [return_id])

    def author(address: str, formula: str | None) -> CellAuthor:
        source = sources.get((return_id, f"{key}!{address}"), ("", 0))[0]
        return _AUTHOR.get(source, "formula" if formula else "person")

    return WorkbookSheetCellsOut(
        sheet=sheet,
        version=newest,
        cells=[
            WorkbookCellOut(
                address=c.address,
                value=c.value,
                formula=c.formula,
                author=author(c.address, c.formula),
                state="formula" if c.formula else "value",
                citation_ids=list(cites.get((return_id, f"{key}!{c.address}"), ())),
                version=newest,
            )
            for c in cells
        ],
        next_range=next_range,
    )


@workbook_router.get(
    f"{_R}/workbook/cells/{{address}}", action="workbook.read",
    response_model=WorkbookCellProvenanceOut, errors=(501,),
)  # fmt: skip
async def entity_cell_route(
    return_id: UUID,
    address: str,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> WorkbookCellProvenanceOut:
    """A cell's provenance (T-05-T27; TXP-11 a, SHL-09): its value, formula, inputs, citations;
    the version-by-version writer is SHL-09's `GET /v1/fields/tax_workbook/…/provenance`."""
    del version
    await _flag_on(ctx)
    _form, _resource = await _workbook_read(ctx, return_id)
    from abacus.modules.review.api import current_values, field_states
    from abacus.modules.tax.workbook_service import WORKBOOK, inputs_of
    from abacus.modules.tax.workbook_service import address as cell_address

    at = cell_address(address)
    values = await current_values(ctx.tenant, WORKBOOK, return_id)
    value = values.get(at.key)
    if value is None:
        raise NotFound("workbook_cell")
    formula = values.get(at.formula_key, {}).get("v")
    state = (await field_states(ctx.tenant, WORKBOOK, return_id, [at.key]))[at.key]
    raw = value.get("v")
    return WorkbookCellProvenanceOut(
        cell=WorkbookCellOut(
            address=at.a1,
            value=None if raw is None else str(raw),
            formula=None if formula is None else str(formula),
            author="formula" if formula else "person",
            state="formula" if formula else "value",
            citation_ids=list(state.citation_ids),
            version=1,
        ),
        writer="Formula" if formula else "Person",
        inputs=inputs_of(None if formula is None else str(formula)),
    )


@workbook_router.put(
    f"{_R}/workbook/cells/{{address}}", action="workbook.edit", response_model=WorkbookCellOut,
    errors=(409,),
)  # fmt: skip
async def entity_edit_cell_route(
    return_id: UUID,
    address: str,
    body: WorkbookCellEditIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookCellOut:
    """`cell_version_conflict`, `cells_locked_by_run` (409); `formula_invalid` (422). T-05-T35
    (DEC-4620): the preparer's edit recomputes its dependents and saves a checkpoint; a
    reviewer's edit becomes a proposal note on the cell and the cell does not change."""
    from abacus.modules.agents.api import work_item_runs
    from abacus.modules.tax.cell_edit import edit_cell
    from abacus.modules.tax.overview import load_return

    await _flag_on(ctx)
    form, resource = await _workbook_read(ctx, return_id)
    await _authorise_edit(ctx, resource)
    loaded = await load_return(ctx, return_id)
    runs = await work_item_runs(ctx.tenant, f"tax_return:{return_id}", 5)
    done = await edit_cell(
        ctx,
        return_id=return_id,
        engagement_id=loaded.facts.engagement_id,
        form=form,
        address_text=address,
        expected_version=body.expected_version,
        value=body.value,
        formula=body.formula,
        run_open=any(r.active for r in runs),
    )
    return WorkbookCellOut(
        address=done.address.partition("!")[2],
        value=done.value,
        formula=done.formula,
        author="person",
        state="flagged" if done.proposal_note_id else ("formula" if done.formula else "value"),
        version=done.version,
        recomputed=list(done.recomputed),
        proposal_note_id=done.proposal_note_id,
        checkpoint_id=done.checkpoint_id,
    )


@workbook_router.get(
    f"{_R}/workbook/export.xlsx", action="workbook.export", response_model=bytes,
    errors=(409, 501),
)  # fmt: skip
async def entity_export_route(
    return_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
    sheet: Annotated[str | None, Query(max_length=40)] = None,
) -> Response:
    """Deterministic xlsx with formulas, formula-escaped; `export_blocked` (409). T-05-T57
    (DEC-4908): the live workbook or a finished run's version, whole or one sheet; byte-identical
    for identical data; audited `workbook.exported`."""
    from abacus.modules.agents.api import work_item_runs
    from abacus.modules.tax.overview import load_return, return_resource
    from abacus.modules.tax.workbook_export import MEDIA_TYPE, export_workbook

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    await _authorise_export(ctx, await return_resource(ctx, loaded))
    runs = await work_item_runs(ctx.tenant, f"tax_return:{return_id}")
    made = await export_workbook(
        ctx,
        return_id=return_id,
        engagement_id=loaded.facts.engagement_id,
        entity=loaded.facts.client_name,
        form=str(loaded.row.form),
        sheet=sheet,
        version=version,
        versions=[
            (r.run_number, r.finished_at)
            for r in sorted(runs, key=lambda r: r.run_number, reverse=True)
            if r.finished_at is not None
        ],
        run_open=any(r.active for r in runs),
    )
    return Response(
        content=made.data,
        media_type=MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{made.filename}"',
            "ETag": f'"{made.sha256}"',
            "Cache-Control": "no-store",
        },
    )


@workbook_router.post(
    f"{_R}/workbook/imports", action="workbook_import.create",
    response_model=WorkbookImportAcceptedOut,
    status_code=201, errors=(409, 413),
)  # fmt: skip
async def entity_import_route(
    return_id: UUID,
    kind: Annotated[ImportKind, Query()],
    request: Request,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookImportAcceptedOut:
    """Raw-body report, parsed as hostile (ADR-052); cells cited as `engine_import`. T-05-T40
    (DEC-4703): CSV or xlsx, at most 5 MB (413) and 2,000 rows; `import_invalid` (422) lists
    sheet, row, column and code; an open run holds the cells (`cells_locked_by_run`, 409)."""
    from abacus.modules.agents.api import work_item_runs
    from abacus.modules.tax.cell_edit import CellsLockedByRun
    from abacus.modules.tax.overview import load_return, return_resource
    from abacus.modules.tax.workbook_imports import MAX_BYTES, record_import

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    await _authorise_import(ctx, await return_resource(ctx, loaded))
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BYTES:
        raise PayloadTooLarge(facts={"limit": MAX_BYTES})
    data = await request.body()
    if len(data) > MAX_BYTES:
        raise PayloadTooLarge(facts={"limit": MAX_BYTES})
    if any(r.active for r in await work_item_runs(ctx.tenant, f"tax_return:{return_id}", 5)):
        raise CellsLockedByRun(facts={"return_id": str(return_id)})
    done = await record_import(
        ctx, return_id=return_id, engagement_id=loaded.facts.engagement_id, kind=kind, data=data
    )
    return WorkbookImportAcceptedOut(import_id=done.import_id, kind=kind, cells=done.cells)


@workbook_router.post(
    f"{_R}/workbook-runs", action="workbook_run.start", response_model=WorkbookRunAcceptedOut,
    status_code=202, errors=(409,),
)  # fmt: skip
async def entity_start_run_route(
    return_id: UUID, body: WorkbookRunIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookRunAcceptedOut:
    """`run_in_progress` (409); a model step without consent waits on inputs (C19). T-05-T31
    (DEC-4616): P-10's engagement run on the `tax.entity_workbook` plan for the scope."""
    from abacus.modules.agents.api import PlanRequest, start_engagement_run, work_item_runs
    from abacus.modules.tax.entity_run_plan import PROVIDER
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    await _authorise_run_start(ctx, await return_resource(ctx, loaded))
    ref = f"tax_return:{return_id}"
    if any(r.active for r in await work_item_runs(ctx.tenant, ref, 5)):
        raise RunInProgress(facts={"return_id": str(return_id)})
    started = await start_engagement_run(
        ctx,
        loaded.facts.engagement_id,
        work_item_ref=ref,
        provider=PROVIDER,
        request=PlanRequest(return_id, body.scope, tuple(body.keys)),
    )
    return WorkbookRunAcceptedOut(run_id=started.run_id, run_no=started.run_number)


@workbook_router.get(f"{_R}/workbook-runs", action="workbook.read", response_model=WorkbookRunsOut)
async def entity_runs_route(return_id: UUID, ctx: Ctx) -> WorkbookRunsOut:
    """TXP-00's run history, newest first (T-05-T31)."""
    from abacus.modules.agents.api import work_item_runs
    from abacus.modules.identity.api import display_names

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    runs = await work_item_runs(ctx.tenant, f"tax_return:{return_id}")
    names = await display_names([r.initiator_user_id for r in runs if r.initiator_user_id])
    return WorkbookRunsOut(
        items=[
            WorkbookRunRowOut(
                run_id=r.run_id,
                run_no=r.run_number,
                started_by=names.get(r.initiator_user_id, "") if r.initiator_user_id else "",
                started_at=r.created_at,
                state=r.state,
            )
            for r in runs
        ]
    )


@workbook_router.get(
    f"{_R}/trial-balance",
    action="workbook.read",
    response_model=WorkbookTrialBalanceOut,
)
async def entity_trial_balance_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["account", "line"], Query()] = "account",
    statement: Annotated[Literal["full", "balance_sheet", "income_statement"], Query()] = "full",
    filter_: Annotated[Literal["unmapped"] | None, Query(alias="filter")] = None,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> WorkbookTrialBalanceOut:
    """T-05-T33 (DEC-4618): C8's tax layers by account or form line; `unmapped` is the whole TB's
    count (the export gate), whatever the filter."""
    from abacus.modules.tax.entity_tb import trial_balance
    from abacus.modules.tax.overview import load_return

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    loaded = await load_return(ctx, return_id)
    rows, unmapped = await trial_balance(
        ctx, return_id, loaded.facts.engagement_id, view, statement, filter_ == "unmapped"
    )
    from abacus.modules.tax.entity_tb import totals

    return WorkbookTrialBalanceOut(
        view=view,
        rows=[
            WorkbookTbRowOut.model_validate({**r.__dict__, "cells": dict(r.cells)}) for r in rows
        ],
        unmapped=unmapped,
        totals=[WorkbookTbTotalOut(**t.__dict__) for t in totals(rows)],
    )


@workbook_router.get(
    f"{_R}/trial-balance/tallies", action="workbook.read", response_model=WorkbookTalliesOut,
)  # fmt: skip
async def entity_tallies_route(return_id: UUID, ctx: Ctx) -> WorkbookTalliesOut:
    """T-05-T33: each column foots to $0; `unmapped` checks the export gate."""
    from abacus.modules.tax.entity_tb import tb_tallies
    from abacus.modules.tax.overview import load_return

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    loaded = await load_return(ctx, return_id)
    found, cards = await tb_tallies(ctx, return_id, loaded.facts.engagement_id)
    return WorkbookTalliesOut(
        items=[
            WorkbookTallyOut(
                key=t.key,
                label=t.label,
                state=t.state,
                difference=t.difference,
                terms=[WorkbookTermOut(**term.__dict__) for term in t.terms],
            )
            for t in found
        ],
        figures=[
            WorkbookFigureOut(
                key=f.key,
                label=f.label,
                amount=f.amount,
                terms=[WorkbookTermOut(**term.__dict__) for term in f.terms],
            )
            for f in cards
        ],
    )


@workbook_router.get(
    f"{_R}/journal-entries", action="adjusted_tb.read", response_model=WorkbookJournalEntriesOut,
)  # fmt: skip
async def entity_journal_entries_route(return_id: UUID, ctx: Ctx) -> WorkbookJournalEntriesOut:
    """T-05-T33: C8's AJEs, RJEs and TJEs on the return (proposing and approving are A-06's)."""
    from abacus.modules.tax.entity_tb import journal_entries

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    return WorkbookJournalEntriesOut(
        items=[
            WorkbookJournalEntryOut(
                id=e.id,
                kind=e.kind,
                reference=e.ref,
                amount=e.amount,
                state=e.status,
                description=e.description,
                approval=e.approval_label,
                lines=[
                    WorkbookJournalEntryLineOut(
                        account_code=ln.account_code,
                        account_name=ln.account_name,
                        debit=ln.debit,
                        credit=ln.credit,
                    )
                    for ln in e.lines
                ],
            )
            for e in await journal_entries(ctx, return_id)
            if e.kind in ("aje", "rje", "tje")
        ]
    )


@workbook_router.get(
    "/form-lines", action="reference_set.read", response_model=WorkbookFormLinesOut
)
async def entity_form_lines_route(
    ctx: Ctx,
    form: Annotated[Literal["1065", "1120-S", "1120", "990"], Query()],
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> WorkbookFormLinesOut:
    """T-05-T37 rest (DEC-4629): the line picker's list, the published set's mappable lines."""
    from abacus.modules.tax.entity_mapping import form_line_choices

    await _flag_on(ctx)
    # The decorator's action is declared, not enforced: a firm-level read of the published set.
    await authorise(ctx, "reference_set.read", Resource.firm(ctx.tenant_id))
    return WorkbookFormLinesOut(
        items=[
            WorkbookFormLineOut(key=c.key, label=c.label)
            for c in await form_line_choices(ctx, form, tax_year, q)
        ]
    )


@workbook_router.post(
    f"{_R}/mappings", action="workbook.edit", response_model=WorkbookMappingProposedOut,
    status_code=201, errors=(409,),
)  # fmt: skip
async def entity_mapping_route(
    return_id: UUID, body: WorkbookMappingIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookMappingProposedOut:
    """TXP-02's line picker (O1). A-03's `account_mapping.edit` requires independence and is an
    audit verb, so the pick is authorised as `workbook.edit` on the return (a person's verb).

    DEC-4629: proposals are the agent's (ADR-161), so a person's pick is not one. The tax
    reviewer's pick maps the account (human only, audited); anyone else's raises a review note
    proposing the line to the reviewer and maps nothing.
    """
    from abacus.modules.tax.entity_mapping import pick_form_line
    from abacus.modules.tax.overview import load_return

    del idempotency_key  # the pick is a set: repeating it writes the same key again
    await _flag_on(ctx)
    _form, resource = await _workbook_read(ctx, return_id)
    await _authorise_edit(ctx, resource)  # a person's pick (agent: deny), on the return
    loaded = await load_return(ctx, return_id)
    out = await pick_form_line(
        ctx, return_id, loaded.facts.engagement_id, body.account_code, body.form_line_key,
        body.rationale,
    )  # fmt: skip
    written = out.note_id if out.state == "flagged" else out.mapping_set_id
    if written is None:  # the pick returns the record it wrote in both states
        raise RuntimeError("the line pick wrote no record")
    return WorkbookMappingProposedOut(
        proposal_id=written, state=out.state, account_code=body.account_code,
        form_line_key=body.form_line_key, note_id=out.note_id,
    )  # fmt: skip


@workbook_router.get(
    f"{_R}/schedules/k", action="workbook.read", response_model=WorkbookScheduleKOut
)
async def entity_schedule_k_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["federal", "state"], Query()] = "federal",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> WorkbookScheduleKOut:
    """T-05-T34 (DEC-4619): 06's lines with 09's partner shares and a tie per line."""
    del version  # one live version until checkpoints version the workbook
    from abacus.modules.tax import entity_schedules as es

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    values = await es.workbook_values(ctx.tenant, return_id)
    partners = [pid for pid, _n in await es.recipients(ctx.tenant, return_id)]
    lines = es.schedule_k(values, partners, view)

    def out(k: es.KLine) -> WorkbookScheduleKLineOut:
        return WorkbookScheduleKLineOut(
            line=k.line,
            label=k.label,
            total=k.total,
            by_partner=[WorkbookScheduleKCellOut(partner_id=p, amount=a) for p, a in k.by_partner],
            tie=k.tie,
        )

    return WorkbookScheduleKOut(
        view=view,
        lines=[out(k) for k in lines],
        analysis=out(es.analysis(lines)) if view == "federal" and lines else None,
    )


@workbook_router.get(
    f"{_R}/schedules/k/lines/{{line}}/breakdown", action="workbook.read",
    response_model=WorkbookBreakdownOut,
)  # fmt: skip
async def entity_schedule_k_breakdown_route(
    return_id: UUID, line: str, ctx: Ctx
) -> WorkbookBreakdownOut:
    """T-05-T34: Form 8825's per-property amounts behind a Schedule K line (sheet 08)."""
    from abacus.modules.tax import entity_schedules as es

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    values = await es.workbook_values(ctx.tenant, return_id)
    return WorkbookBreakdownOut(
        line=line,
        rows=[
            WorkbookBreakdownRowOut(property_name=n, amount=a)
            for n, a in es.breakdown(values, line)
        ],
    )


@workbook_router.get(
    f"{_R}/capital-accounts", action="workbook.read", response_model=WorkbookCapitalAccountsOut,
)  # fmt: skip
async def entity_capital_accounts_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["by_partner", "by_movement"], Query()] = "by_partner",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> WorkbookCapitalAccountsOut:
    """T-05-T34: 05's partner rows (tax basis), server totals and the Item L facts."""
    del version
    from abacus.modules.tax import entity_schedules as es

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    values = await es.workbook_values(ctx.tenant, return_id)
    known = {n: pid for pid, n in await es.recipients(ctx.tenant, return_id)}
    rows = es.capital_rows(values, return_id, known)
    totals = es.capital_totals(rows)
    found = es.item_l(rows, es.m2_as_drafted(values))
    extras = [es.capital_extras(values, n) for n in range(2, len(rows) + 2)]

    def total_of(key: str) -> Decimal | None:
        present = [v for e in extras if (v := e[key]) is not None]
        return sum(present, Decimal(0)) if present else None

    book = total_of("ending_704b")
    return WorkbookCapitalAccountsOut(
        view=view,
        basis="tax",
        rows=[
            WorkbookCapitalRowOut(
                partner_id=r.partner_id,
                name=r.name,
                beginning=r.beginning,
                contributions=r.contributions,
                income=r.income,
                distributions=r.distributions,
                ending=r.ending,
                row=n,
                **extras[n - 2],
            )
            for n, r in enumerate(rows, start=2)
        ],
        tie=es.capital_tie(rows),
        totals=WorkbookCapitalTotalsOut(
            **totals.__dict__,
            tax_exempt=total_of("tax_exempt"),
            transfers=total_of("transfers"),
            ending_704b=book,
        ),
        item_l=WorkbookItemLOut(**found.__dict__),
        book_tie="pending" if book is None else ("tie" if book == found.m2_ending else "off"),
        derives_tie="tie" if sum((r.ending for r in rows), Decimal(0)) == totals.ending else "off",
    )


@workbook_router.get(f"{_R}/schedules/m2", action="workbook.read", response_model=WorkbookM2Out)
async def entity_m2_route(
    return_id: UUID,
    ctx: Ctx,
    variant: Annotated[Literal["as_drafted", "with_fix"], Query()] = "as_drafted",
) -> WorkbookM2Out:
    """T-05-T34: 07 as drafted, or rebuilt from 05's partner totals (what the fix writes)."""
    from abacus.modules.tax import entity_schedules as es

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    values = await es.workbook_values(ctx.tenant, return_id)
    rows = es.capital_rows(values, return_id, {})
    m2 = es.m2_as_drafted(values) if variant == "as_drafted" else es.m2_with_fix(values, rows)
    found = es.item_l(rows, m2)
    return WorkbookM2Out(
        variant=variant,
        beginning=m2.beginning,
        ending=m2.ending,
        tie=m2.tie,
        difference=m2.difference,
        lines=[WorkbookM2LineOut(line=n, label=label, amount=a) for n, label, a in m2.lines],
        item_l=WorkbookItemLOut(**found.__dict__),
    )


def _draft(body: WorkbookAllocationDraftIn) -> Draft:
    from abacus.modules.tax.allocation_structure import Draft, DraftRung, rung_params

    return Draft(
        kind=body.kind,
        method=body.method,
        convention=body.convention,
        income=body.income,
        segment_amounts=tuple(body.segment_amounts),
        rungs=tuple(
            DraftRung(n, r.key, rung_params(r.key, r.percentage, r.amount), tuple(r.citation_ids))
            for n, r in enumerate(body.rungs, start=1)
        ),
        citation_ids=tuple(dict.fromkeys(c for r in body.rungs for c in r.citation_ids)),
    )


def _tiers(
    rows: list[WorkbookAllocationPeriodOut], distributable: Decimal | None
) -> list[WorkbookAllocationPeriodOut]:
    """Waterfall rungs (`r<n>` keys) with prior tiers, available and remaining (code's sums)."""
    if distributable is None:
        return rows
    out: list[WorkbookAllocationPeriodOut] = []
    prior = Decimal(0)
    for r in rows:
        available = distributable - prior
        out.append(
            r.model_copy(
                update={
                    "prior": prior if prior else None,
                    "available": available,
                    "remaining": available - r.amount,
                }
            )
        )
        prior += r.amount
    return out


def _rung_out(priority: int, rule_type: str, params: dict[str, str]) -> WorkbookRungOut:
    from abacus.modules.tax.allocation_structure import PERCENT_PARAM

    key = PERCENT_PARAM.get(rule_type)
    pct = params.get(key) if key else None
    days = params.get("days") if rule_type == "preferred_return" else None
    return WorkbookRungOut(
        key=rule_type,
        label=rule_type.replace("_", " ").capitalize(),
        percentage=None if pct is None else Decimal(pct),
        amount=None if days is None else Decimal(days),
    )


async def _structure_out(
    ctx: AuthContext, return_id: UUID, resource: Resource, version: int | None
) -> WorkbookAllocationStructureOut:
    from abacus.modules.tax import allocation_structure as alloc

    found = await alloc.view(ctx.tenant, return_id, version)
    actions = cast(
        list[WorkbookAction],
        [a for a in await allowed_actions(ctx, resource) if a == "allocation_structure.edit"],
    )
    names = {p.id: p for p in found.partners}
    totals: dict[UUID, Decimal] = {}
    for r in found.results:
        totals[r.partner_id] = totals.get(r.partner_id, Decimal(0)) + r.amount
    row = found.row
    periods: dict[str, Decimal] = {}
    for r in found.results:
        key = r.period_key if r.rung_priority is None else f"r{r.rung_priority}"
        periods[key] = periods.get(key, Decimal(0)) + r.amount
    return WorkbookAllocationStructureOut(
        version=0 if row is None else row.version_no,
        kind="straight_percentage" if row is None else row.kind,
        status=found.status,
        rungs=[_rung_out(r.priority, r.rule_type, dict(r.params)) for r in found.rungs],
        seen_hash="" if row is None else f"sha256:{row.content_hash}",
        allowed_actions=actions,
        structure_id=None if row is None else row.id,
        sign_off_target_id=None if row is None else row.sign_off_target,
        latest_version=found.latest_version,
        method="interim_closing" if row is None else row.method,
        convention="calendar_day" if row is None else row.convention,
        proposed_by=None if row is None else row.proposed_by_kind,
        income=None if row is None else row.income,
        distributable=None if row is None else row.distributable,
        periods=_tiers(
            [WorkbookAllocationPeriodOut(key=k, amount=v) for k, v in periods.items()],
            None if row is None or row.kind != "targeted_waterfall" else row.distributable,
        ),
        partners=[
            WorkbookAllocationPartnerOut(
                partner_id=p.id,
                name=p.name,
                kind=cast(Literal["gp", "lp", "member", "shareholder"], p.kind),
                total=totals.get(p.id, Decimal(0)),
                **(
                    {
                        "beginning": p.beginning_capital,
                        "target": p.beginning_capital + totals.get(p.id, Decimal(0)),
                    }
                    if row is not None and row.kind == "targeted_waterfall"
                    else {}
                ),
            )
            for p in names.values()
        ],
        results=[
            WorkbookAllocationResultOut(
                partner_id=r.partner_id,
                period_key=r.period_key,
                rung_priority=r.rung_priority,
                amount=r.amount,
            )
            for r in found.results
        ],
        citation_ids=[] if row is None else list(row.citation_ids),
    )


@workbook_router.get(
    f"{_R}/allocation-structure", action="allocation_structure.read",
    response_model=WorkbookAllocationStructureOut,
)  # fmt: skip
async def entity_allocation_route(
    return_id: UUID, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> WorkbookAllocationStructureOut:
    """T-05-T41 (DEC-4701): the newest version (or `version`), its rungs, stored results and
    the partners' totals; `seen_hash` is what TXP-06's L3 names."""
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, "allocation_structure.read", resource)
    return await _structure_out(ctx, return_id, resource, version)


@workbook_router.put(
    f"{_R}/allocation-structure/draft", action="allocation_structure.edit",
    response_model=WorkbookAllocationStructureOut, errors=(409,),
)  # fmt: skip
async def entity_allocation_draft_route(
    return_id: UUID, body: WorkbookAllocationDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookAllocationStructureOut:
    """A new version Pending approval (`structure_version_conflict`, 409; a manager or partner
    only, `structure_editor_required`, 403); approval is P-04's L3 sign-off on it."""
    from abacus.modules.tax.allocation_structure import save_draft
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await _authorise_structure_edit(ctx, resource)
    await save_draft(
        ctx,
        return_id=return_id,
        engagement_id=loaded.facts.engagement_id,
        year=int(loaded.row.tax_year),
        expected_version=body.expected_version,
        draft=_draft(body),
    )
    return await _structure_out(ctx, return_id, resource, None)


@workbook_router.post(
    f"{_R}/allocation-structure/preview", action="allocation_structure.read",
    response_model=WorkbookAllocationStructureOut,
)  # fmt: skip
async def entity_allocation_preview_route(
    return_id: UUID, body: WorkbookAllocationDraftIn, ctx: Ctx
) -> WorkbookAllocationStructureOut:
    """Recompute without persistence (TXP-06 d: the back-solve shows Pending until Save)."""
    from abacus.modules.tax.allocation_structure import preview
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, "allocation_structure.read", resource)
    draft = _draft(body)
    found = await preview(ctx, return_id, int(loaded.row.tax_year), draft)
    return WorkbookAllocationStructureOut(
        version=body.expected_version,
        kind=draft.kind,
        status="editing",
        rungs=list(body.rungs),
        seen_hash="",
        allowed_actions=[],
        method=draft.method,
        convention=draft.convention,
        income=found.total,
        distributable=found.distributable,
        periods=_tiers(
            [
                WorkbookAllocationPeriodOut(
                    key=p.key, starts_on=p.starts_on, ends_on=p.ends_on, amount=p.amount
                )
                for p in found.periods
            ],
            found.distributable,
        ),
        results=[
            WorkbookAllocationResultOut(
                partner_id=r.partner_id,
                period_key=r.period_key,
                rung_priority=r.rung_priority,
                amount=r.amount,
            )
            for r in found.results
        ],
        checks=dict(found.checks),
        gp_profit_percent=found.gp_profit_percent,
        persisted=False,
    )


@workbook_router.post(
    f"{_R}/allocation-structure/approve", action="sign_off.create",
    response_model=WorkbookAllocationApprovedOut, status_code=201, errors=(409,),
)  # fmt: skip
async def entity_allocation_approve_route(
    return_id: UUID, body: WorkbookAllocationApproveIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookAllocationApprovedOut:
    """TXP-06 c2: the L3 sign-off (P-04's rules: a person only, a manager or partner, not the
    version's preparer; `content_changed` when the structure moved), the approved version and the
    capital and K-1 re-run (none while a run is open)."""
    from abacus.modules.tax.allocation_structure import approve
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    await authorise(ctx, "allocation_structure.read", await return_resource(ctx, loaded))
    done = await approve(
        ctx,
        return_id=return_id,
        engagement_id=loaded.facts.engagement_id,
        seen_hash=body.seen_hash,
        statement_version=body.statement_version,
    )
    return WorkbookAllocationApprovedOut(
        sign_off_id=done.sign_off_id,
        structure_id=done.structure_id,
        run_id=done.run_id,
        run_no=done.run_no,
    )


@workbook_router.get(f"{_R}/sections", action="workbook.read", response_model=WorkbookSectionsOut)
async def entity_sections_route(return_id: UUID, ctx: Ctx) -> WorkbookSectionsOut:
    """T-05-T42 (DEC-4705): the six sections, their tie-outs, signed and stale levels."""
    from abacus.modules.tax.entity_sections import sections_view
    from abacus.modules.tax.overview import load_return

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    loaded = await load_return(ctx, return_id)
    found = await sections_view(ctx, return_id, loaded.facts.engagement_id)
    return WorkbookSectionsOut(
        items=[
            WorkbookSectionOut(
                key=s.key,
                title=s.title,
                tallies=[
                    WorkbookTallyOut(
                        key=t.key, label=t.label, state=t.state, difference=t.difference
                    )
                    for t in s.tallies
                ],
                signed_levels=list(s.signed_levels),
                section_id=s.section_id,
                seen_hash=f"sha256:{s.content_hash}",
                stale_levels=list(s.stale_levels),
            )
            for s in found
        ]
    )


@workbook_router.post(
    f"{_R}/sections/{{key}}/sign-off", action="sign_off.create",
    response_model=WorkbookSignOffRecordedOut, status_code=201, errors=(409,),
)  # fmt: skip
async def entity_section_sign_off_route(
    return_id: UUID,
    key: str,
    body: WorkbookSectionSignOffIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookSignOffRecordedOut:
    """Tie-out precheck (`tie_out_off`, 409, unless a note is given), then P-04's sign-off
    (`level_not_permitted`, 403; `preparer_cannot_review`). T-05-T42 (DEC-4705)."""
    from abacus.modules.tax.entity_sections import sign_section
    from abacus.modules.tax.overview import load_return

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    loaded = await load_return(ctx, return_id)
    done = await sign_section(
        ctx,
        return_id=return_id,
        engagement_id=loaded.facts.engagement_id,
        key=key,
        level=int(body.level.removeprefix("l")),
        seen_hash=body.seen_hash,
        note=body.note,
        statement_version=body.statement_version,
    )
    return WorkbookSignOffRecordedOut(sign_off_id=done.sign_off_id)


@workbook_router.get(
    f"{_R}/issues", action="issue.read", response_model=WorkbookReturnIssuesOut, errors=(501,)
)
async def entity_issues_route(
    return_id: UUID,
    ctx: Ctx,
    section: Annotated[str | None, Query(max_length=40)] = None,
    status: Annotated[str | None, Query(max_length=40)] = None,
    step: Annotated[str | None, Query(max_length=60)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    show_resolved: Annotated[bool, Query()] = False,
) -> WorkbookReturnIssuesOut:
    """TXP-10's queue (T-05-T51, DEC-4903): Waiting on the client and Review points, counts over
    the open issues before the filters (the badge), `by_step` for TXP-00."""
    from abacus.modules.tax.entity_issues import issue_queue

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    queue = await issue_queue(
        ctx, return_id, section=section, status=status, step=step, q=q,
        show_resolved=show_resolved,
    )  # fmt: skip
    return WorkbookReturnIssuesOut(
        items=[
            WorkbookReturnIssueOut(
                id=i.id, title=i.title, section=i.section, step=i.step, status=i.status,
                kind=i.kind, priority=i.priority, source_kind=i.source_kind,
                category_path=i.category_path, blocks=list(i.blocks),
                assignee=None if i.assignee is None else WorkbookIssueAssigneeOut(
                    kind=i.assignee.kind, user_id=i.assignee.user_id, name=i.assignee.name
                ),
                cells=[
                    WorkbookIssueCellLinkOut(sheet=str(c.get("sheet", "")),
                                             range=str(c.get("range", "")))
                    for c in i.links
                ],
                request_item_id=i.request_item_id, version=i.version, created_at=i.created_at,
                allowed_actions=list(i.allowed_actions),
            )
            for i in queue.items
        ],
        by_section=queue.by_section,
        by_step=queue.by_step,
        open_total=queue.open_total,
        resolved_total=queue.resolved_total,
        sections=[
            WorkbookIssueSectionOut(key=k, title=t, count=n)  # type: ignore[arg-type] -- the queue lists only the two open sections
            for k, t, n in queue.sections
        ],
    )  # fmt: skip


@workbook_router.get(
    f"{_R}/issue-assignees", action="issue.read", response_model=WorkbookIssueAssigneesOut
)
async def entity_issue_assignees_route(return_id: UUID, ctx: Ctx) -> WorkbookIssueAssigneesOut:
    """TXP-10's assignee picker (T-05-T51): the team, the Accrued Agent, client contacts."""
    from abacus.modules.tax.entity_issues import assignee_options

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    return WorkbookIssueAssigneesOut(
        items=[
            WorkbookIssueAssigneeOptionOut(kind=o.kind, id=o.id, name=o.name, detail=o.detail)
            for o in await assignee_options(ctx, return_id)
        ]
    )


@workbook_router.post(
    f"{_R}/issues/{{issue_id}}/send-to-client", action="issue.send_to_client",
    response_model=WorkbookIssueSentOut, errors=(409,),
)  # fmt: skip
async def entity_issue_send_route(
    return_id: UUID, issue_id: UUID, body: WorkbookIssueSendIn, ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookIssueSentOut:  # fmt: skip
    """SHL-15 → POR-04 (T-05-T51, DEC-4904): only the issue's client wording; 409
    `client_wording_missing` without one."""
    from abacus.modules.tax.entity_issues import send_to_client

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    item = await send_to_client(
        ctx, return_id, issue_id, seen_version=body.seen_version, contact_id=body.contact_id,
        due_on=body.due_on,
    )  # fmt: skip
    return WorkbookIssueSentOut(request_item_id=item)


@workbook_router.post(
    f"{_R}/issues/{{issue_id}}/reminders", action="follow_up.draft",
    response_model=WorkbookIssueReminderOut, status_code=202, errors=(409,),
)  # fmt: skip
async def entity_issue_remind_route(
    return_id: UUID, issue_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookIssueReminderOut:
    """A follow-up draft from the firm's C16 Reminder template on the issue's request item."""
    from abacus.modules.tax.entity_issues import remind

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    return WorkbookIssueReminderOut(drafts=await remind(ctx, return_id, issue_id))


@workbook_router.post(
    f"{_R}/issues/{{issue_id}}/resolve", action="issue.resolve",
    response_model=WorkbookIssueResolvedOut, errors=(409,),
)  # fmt: skip
async def entity_issue_resolve_route(
    return_id: UUID, issue_id: UUID, body: WorkbookIssueResolveIn, ctx: Ctx
) -> WorkbookIssueResolvedOut:
    """P-04's resolve with a required note when no fix was approved (422
    `resolution_note_required`); the note is sealed, audited by hash."""
    from abacus.modules.tax.entity_issues import resolve

    await _flag_on(ctx)
    await _workbook_read(ctx, return_id)
    await resolve(ctx, return_id, issue_id, seen_version=body.seen_version, note=body.note)
    return WorkbookIssueResolvedOut(issue_id=issue_id, noted=bool((body.note or "").strip()))


@workbook_router.get(
    f"{_R}/memo", action="tax_memo.read", response_model=WorkbookMemoOut, errors=(501,)
)
async def entity_memo_route(return_id: UUID, ctx: Ctx) -> WorkbookMemoOut:
    """TXP-01 (T-05-T54, DEC-4909): sections, status (stale computed on cited figures) and the
    moved figures in words."""
    from abacus.modules.tax.memo_service import read_memo

    await _flag_on(ctx)
    await _memo_read(ctx, return_id)
    memo = await read_memo(ctx, return_id)
    return WorkbookMemoOut(
        status=memo.status,
        sections=[
            WorkbookMemoSectionOut(
                key=s.key,
                title=s.title,
                body=s.body,
                human_owned=s.human_owned,
                version=memo.version,
            )
            for s in memo.sections
        ],
        seen_hash=memo.seen_hash,
        stale_fields=memo.stale_fields,
        allowed_actions=[],
    )


async def _memo_read(ctx: AuthContext, return_id: UUID) -> Resource:
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, "tax_memo.read", resource)
    return resource


@workbook_router.post(
    f"{_R}/memo/draft", action="tax_memo.draft",
    response_model=WorkbookAcceptedOut, status_code=202,
    errors=(409, 501),
)  # fmt: skip
async def entity_memo_draft_route(
    return_id: UUID, body: WorkbookMemoDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookAcceptedOut:
    """A memo run; `consent_required` (409) without both §7216 consents. T-05-T54: no sections
    named regenerates a stale memo's affected sections only; a person's sections are kept."""
    from abacus.modules.tax.memo_service import start_draft

    await _flag_on(ctx)
    resource = await _memo_read(ctx, return_id)
    await _authorise_memo_draft(ctx, resource)
    run_id = await start_draft(ctx, return_id, body.sections)
    return WorkbookAcceptedOut(run_id=run_id)


@workbook_router.patch(
    f"{_R}/memo/sections/{{key}}", action="tax_memo.edit", response_model=WorkbookMemoSectionOut,
    errors=(409, 501),
)  # fmt: skip
async def entity_memo_section_route(
    return_id: UUID,
    key: str,
    body: WorkbookMemoSectionEditIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookMemoSectionOut:
    """A person's section edit (T-05-T54): human-owned from now on; 409
    `memo_version_conflict`."""
    from abacus.modules.tax.memo_service import edit_section

    await _flag_on(ctx)
    resource = await _memo_read(ctx, return_id)
    await _authorise_memo_edit(ctx, resource)
    done = await edit_section(
        ctx, return_id, key, expected_version=body.expected_version, body=body.body
    )
    return WorkbookMemoSectionOut(
        key=done.key, title=done.title, body=done.body, human_owned=True,
        version=body.expected_version + 1,
    )  # fmt: skip


@workbook_router.post(
    f"{_R}/memo/adopt", action="sign_off.create", response_model=WorkbookSignOffRecordedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_memo_adopt_route(
    return_id: UUID, body: WorkbookMemoAdoptIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookSignOffRecordedOut:
    """The preparer's L1 sign-off on the memo (`seen_hash`); the reviewer's L2 is P-04's
    (T-05-T54: `POST …/memo/approve`)."""
    from abacus.modules.tax.memo_service import sign_memo

    await _flag_on(ctx)
    await _memo_read(ctx, return_id)
    return WorkbookSignOffRecordedOut(
        sign_off_id=await sign_memo(ctx, return_id, level=1, seen_hash=body.seen_hash)
    )


@workbook_router.post(
    f"{_R}/memo/approve", action="sign_off.create", response_model=WorkbookSignOffRecordedOut,
    status_code=201, errors=(409,),
)  # fmt: skip
async def entity_memo_approve_route(
    return_id: UUID, body: WorkbookMemoAdoptIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookSignOffRecordedOut:
    """T-05-T54 (DEC-4910): the reviewer's L2 on the memo; never the preparer (403
    `preparer_cannot_approve`); approval writes the opportunities."""
    from abacus.modules.tax.memo_service import sign_memo

    await _flag_on(ctx)
    await _memo_read(ctx, return_id)
    return WorkbookSignOffRecordedOut(
        sign_off_id=await sign_memo(ctx, return_id, level=2, seen_hash=body.seen_hash)
    )


@workbook_router.get(
    f"{_R}/opportunities",
    action="tax_memo.read",
    response_model=WorkbookOpportunitiesOut,
    errors=(501,),
)
async def entity_opportunities_route(return_id: UUID, ctx: Ctx) -> WorkbookOpportunitiesOut:
    """T-05-T54: the approved memo's opportunities."""
    from abacus.modules.tax.memo_service import opportunities

    await _flag_on(ctx)
    await _memo_read(ctx, return_id)
    return WorkbookOpportunitiesOut(
        items=[
            WorkbookOpportunityOut(key=str(i), title=t)
            for i, t in await opportunities(ctx, return_id)
        ]
    )


@workbook_router.get(
    f"{_R}/reconciliation", action="tax_reconciliation.read",
    response_model=WorkbookReconciliationOut,
)  # fmt: skip
async def entity_reconciliation_route(
    return_id: UUID, ctx: Ctx, checkpoint: Annotated[UUID | None, Query()] = None
) -> WorkbookReconciliationOut:
    """T-05-T61 (DEC-4934): the engine's approved figures beside the workbook's, by code."""
    from abacus.modules.tax.entity_reconciliation import SHADOW_LABEL, differences, reconcile
    from abacus.modules.tax.overview import load_return, return_resource

    await _flag_on(ctx)
    loaded = await load_return(ctx, return_id)
    await authorise(ctx, "tax_reconciliation.read", await return_resource(ctx, loaded))
    rows = await reconcile(ctx.tenant, return_id)
    explain = {r.key for r in differences(rows)}
    return WorkbookReconciliationOut(
        checkpoint_id=checkpoint,
        rows=[
            WorkbookReconciliationRowOut(
                field_key=r.key, accrued=r.accrued, engine=r.engine, label=r.label,
                differs=r.key in explain,
            )
            for r in rows
        ],
        differences=len(explain),
        accrued_label=SHADOW_LABEL,
    )  # fmt: skip


__all__ = ["workbook_router"]
