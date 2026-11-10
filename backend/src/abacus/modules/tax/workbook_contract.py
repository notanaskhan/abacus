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
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ENTITY_WORKSPACE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

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


class GeneralInformationOut(BaseModel):
    model_config = _cfg()

    return_id: Annotated[UUID, Internal]
    entity_name: Annotated[str, Confidential]
    form: Annotated[Literal["1065", "1120-S", "1120", "990"], Internal]
    tax_year: Annotated[int, Internal]
    ein_last4: Annotated[str | None, Field(pattern=r"^\d{4}$"), Confidential] = None
    accounting_method: Annotated[str | None, Internal] = None
    preparer_name: Annotated[str | None, Confidential] = None
    reviewer_name: Annotated[str | None, Confidential] = None
    signer_name: Annotated[str | None, Confidential] = None


class PartnerOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    name: Annotated[str, Tri]
    tin_last4: Annotated[str | None, Field(pattern=r"^\d{4}$"), Tri] = None  # never the full TIN
    kind: Annotated[Literal["general", "limited", "llc_member"], Internal]


class OwnershipPeriodOut(BaseModel):
    model_config = _cfg()

    starts_on: Annotated[date, Internal]
    ends_on: Annotated[date, Internal]
    shares: Annotated[dict[str, Decimal], Tri]  # partner id → percentage (exact decimal)


class InterestTransferOut(BaseModel):
    model_config = _cfg()

    on: Annotated[date, Internal]
    from_partner_id: Annotated[UUID, Internal]
    to_partner_id: Annotated[UUID, Internal]
    percentage: Annotated[Decimal, Tri]
    citation_id: Annotated[UUID | None, Internal] = None


class PartnersOut(BaseModel):
    model_config = _cfg()

    version: Annotated[int, Internal]
    partners: Annotated[list[PartnerOut], Tri]
    periods: Annotated[list[OwnershipPeriodOut], Tri]
    transfers: Annotated[list[InterestTransferOut], Tri]
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class OwnershipIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    periods: Annotated[list[OwnershipPeriodOut], Field(min_length=1, max_length=24), Tri]
    transfers: Annotated[list[InterestTransferOut], Field(max_length=50), Tri] = Field(
        default_factory=list[InterestTransferOut]
    )
    citation_note: Annotated[str, Field(min_length=1, max_length=500), Tri]


# --- the workbook ------------------------------------------------------------------------------


class SheetOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]  # "05_capital"
    title: Annotated[str, Internal]
    flagged: Annotated[int, Field(ge=0), Internal] = 0
    imported_from: Annotated[str | None, Internal] = None  # an import-mode sheet's source


class WorkbookOut(BaseModel):
    model_config = _cfg()

    return_id: Annotated[UUID, Internal]
    version: Annotated[int, Internal]
    sheets: Annotated[list[SheetOut], Internal]
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class CellOut(BaseModel):
    model_config = _cfg()

    address: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[0-9]{1,6}$"), Internal]
    value: Annotated[str | None, Tri] = None  # exact decimal or text, as stored
    formula: Annotated[str | None, Tri] = None  # E13's closed grammar (ADR-237)
    author: Annotated[CellAuthor, Internal]
    state: Annotated[CellState, Internal]
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    version: Annotated[int, Internal]


class SheetCellsOut(BaseModel):
    model_config = _cfg()

    sheet: Annotated[str, Internal]
    version: Annotated[int, Internal]
    cells: Annotated[list[CellOut], Tri]
    next_range: Annotated[str | None, Internal] = None


class CellProvenanceOut(BaseModel):
    model_config = _cfg()

    cell: Annotated[CellOut, Tri]
    writer: Annotated[str, Confidential]  # "Run 3 · started by Samuel Ito", "Olivia Brandt"
    inputs: Annotated[list[str], Internal] = Field(default_factory=list[str])
    issue_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class CellEditIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    value: Annotated[str | None, Field(max_length=200), Tri] = None
    formula: Annotated[str | None, Field(max_length=2000), Tri] = None


class ImportAcceptedOut(BaseModel):
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


class TbRowOut(BaseModel):
    model_config = _cfg()

    account_code: Annotated[str, Confidential]
    account_name: Annotated[str, Confidential]
    form_line_key: Annotated[str | None, Internal] = None
    unadjusted: Annotated[Decimal, Tri]
    aje: Annotated[Decimal, Tri]
    rje: Annotated[Decimal, Tri]
    tje: Annotated[Decimal, Tri]
    tax_basis: Annotated[Decimal, Tri]


class TrialBalanceOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["account", "line"], Internal]
    rows: Annotated[list[TbRowOut], Tri]
    unmapped: Annotated[int, Field(ge=0), Internal]


class TallyOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    state: Annotated[TallyState, Internal]
    difference: Annotated[MaybeMoney, Tri] = None


class TalliesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TallyOut], Tri]


class JournalEntryOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    kind: Annotated[Literal["aje", "rje", "tje"], Internal]
    reference: Annotated[str, Internal]  # "TJE-3"
    amount: Annotated[Decimal, Tri]
    state: Annotated[str, Internal]


class JournalEntriesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[JournalEntryOut], Tri]


class FormLineOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]


class FormLinesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[FormLineOut], Internal]


class MappingIn(BaseModel):
    model_config = _cfg()

    account_code: Annotated[str, Field(min_length=1, max_length=40), Confidential]
    form_line_key: Annotated[str, Field(min_length=1, max_length=80), Internal]
    rationale: Annotated[str | None, Field(max_length=500), Confidential] = None


class MappingProposedOut(BaseModel):
    model_config = _cfg()

    proposal_id: Annotated[UUID, Internal]


# --- Schedule K, capital, M-2 ------------------------------------------------------------------


class ScheduleKCellOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    amount: Annotated[Decimal, Tri]


class ScheduleKLineOut(BaseModel):
    model_config = _cfg()

    line: Annotated[str, Internal]  # "1", "2", "13d"
    label: Annotated[str, Internal]
    total: Annotated[Decimal, Tri]
    by_partner: Annotated[list[ScheduleKCellOut], Tri]
    tie: Annotated[TallyState, Internal]


class ScheduleKOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["federal", "state"], Internal]
    lines: Annotated[list[ScheduleKLineOut], Tri]


class BreakdownRowOut(BaseModel):
    model_config = _cfg()

    property_name: Annotated[str, Confidential]
    amount: Annotated[Decimal, Tri]


class BreakdownOut(BaseModel):
    model_config = _cfg()

    line: Annotated[str, Internal]
    rows: Annotated[list[BreakdownRowOut], Tri]


class CapitalRowOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    beginning: Annotated[Decimal, Tri]
    contributions: Annotated[Decimal, Tri]
    income: Annotated[Decimal, Tri]
    distributions: Annotated[Decimal, Tri]
    ending: Annotated[Decimal, Tri]


class CapitalAccountsOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["by_partner", "by_movement"], Internal]
    basis: Annotated[Literal["tax", "gaap", "section_704b"], Internal]
    rows: Annotated[list[CapitalRowOut], Tri]
    tie: Annotated[TallyState, Internal]


class M2Out(BaseModel):
    model_config = _cfg()

    variant: Annotated[Literal["as_drafted", "with_fix"], Internal]
    beginning: Annotated[Decimal, Tri]
    ending: Annotated[Decimal, Tri]
    tie: Annotated[TallyState, Internal]
    difference: Annotated[MaybeMoney, Tri] = None


# --- the allocation structure ------------------------------------------------------------------


class RungOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    amount: Annotated[MaybeMoney, Tri] = None
    percentage: Annotated[Decimal | None, Tri] = None
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class AllocationStructureOut(BaseModel):
    model_config = _cfg()

    version: Annotated[int, Internal]
    kind: Annotated[StructureKind, Internal]
    status: Annotated[StructureStatus, Internal]
    rungs: Annotated[list[RungOut], Tri]
    seen_hash: Annotated[str, Internal]  # what an L3 sign-off names (P-04)
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class AllocationDraftIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    kind: Annotated[StructureKind, Internal]
    rungs: Annotated[list[RungOut], Field(min_length=1, max_length=20), Tri]


# --- sections, issues, the memo, reconciliation ------------------------------------------------


class SectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Internal]
    tallies: Annotated[list[TallyOut], Tri]
    signed_levels: Annotated[list[str], Internal]


class SectionsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SectionOut], Tri]


class SectionSignOffIn(BaseModel):
    model_config = _cfg()

    level: Annotated[Literal["l2", "l3"], Internal]
    seen_hash: Annotated[str, Internal]
    note: Annotated[str | None, Field(max_length=500), Confidential] = None


class SignOffRecordedOut(BaseModel):
    model_config = _cfg()

    sign_off_id: Annotated[UUID, Internal]


class ReturnIssueOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    section: Annotated[str | None, Internal] = None
    step: Annotated[str | None, Internal] = None
    status: Annotated[str, Internal]


class ReturnIssuesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[ReturnIssueOut], Confidential]
    by_section: Annotated[dict[str, int], Internal]
    by_step: Annotated[dict[str, int], Internal]


class MemoSectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Internal]
    body: Annotated[str, Tri]
    human_owned: Annotated[bool, Internal]
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    version: Annotated[int, Internal]


class MemoOut(BaseModel):
    model_config = _cfg()

    status: Annotated[MemoStatus, Internal]
    sections: Annotated[list[MemoSectionOut], Tri]
    seen_hash: Annotated[str, Internal]
    stale_fields: Annotated[list[str], Internal] = Field(default_factory=list[str])
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class MemoDraftIn(BaseModel):
    model_config = _cfg()

    sections: Annotated[list[str], Field(max_length=12), Internal] = Field(
        default_factory=list[str]
    )


class MemoSectionEditIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    body: Annotated[str, Field(min_length=1, max_length=20_000), Tri]


class MemoAdoptIn(BaseModel):
    model_config = _cfg()

    seen_hash: Annotated[str, Internal]


class OpportunityOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Confidential]


class OpportunitiesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[OpportunityOut], Confidential]


class ReconciliationRowOut(BaseModel):
    model_config = _cfg()

    field_key: Annotated[str, Internal]
    accrued: Annotated[MaybeMoney, Tri] = None
    engine: Annotated[MaybeMoney, Tri] = None
    issue_id: Annotated[UUID | None, Internal] = None


class ReconciliationOut(BaseModel):
    model_config = _cfg()

    checkpoint_id: Annotated[UUID | None, Internal] = None
    rows: Annotated[list[ReconciliationRowOut], Tri]
    differences: Annotated[int, Field(ge=0), Internal]


class AcceptedOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

workbook_router = AbacusRouter(prefix="/v1", tags=["tax workbook"])
_R = "/tax-returns/{return_id}"


async def _flag_on(ctx: AuthContext) -> None:
    """A client principal never reaches the workspace; the flag off answers 404."""
    if ctx.client or not await flag_enabled(ctx.tenant, TAX_ENTITY_WORKSPACE):
        raise NotFound(TAX_ENTITY_WORKSPACE.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@workbook_router.get(
    f"{_R}/general-information", action="tax_return.read",
    response_model=GeneralInformationOut, errors=(501,),
)  # fmt: skip
async def entity_general_information_route(return_id: UUID, ctx: Ctx) -> GeneralInformationOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/partners", action="tax_return.read", response_model=PartnersOut, errors=(501,)
)
async def entity_partners_route(return_id: UUID, ctx: Ctx) -> PartnersOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.put(
    f"{_R}/ownership", action="tax_ownership.edit", response_model=PartnersOut,
    errors=(409, 501),
)  # fmt: skip
async def entity_ownership_route(
    return_id: UUID, body: OwnershipIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> PartnersOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/workbook", action="workbook.read", response_model=WorkbookOut, errors=(501,)
)
async def workbook_route(return_id: UUID, ctx: Ctx) -> WorkbookOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/workbook/sheets/{{sheet}}", action="workbook.read", response_model=SheetCellsOut,
    errors=(501,),
)  # fmt: skip
async def entity_sheet_route(
    return_id: UUID,
    sheet: str,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
    range_: Annotated[str | None, Query(alias="range", max_length=40)] = None,
) -> SheetCellsOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/workbook/cells/{{address}}", action="workbook.read",
    response_model=CellProvenanceOut, errors=(501,),
)  # fmt: skip
async def entity_cell_route(
    return_id: UUID,
    address: str,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> CellProvenanceOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.put(
    f"{_R}/workbook/cells/{{address}}", action="workbook.edit", response_model=CellOut,
    errors=(409, 501),
)  # fmt: skip
async def entity_edit_cell_route(
    return_id: UUID, address: str, body: CellEditIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> CellOut:
    """`cell_version_conflict`, `cells_locked_by_run` (409); `formula_invalid` (422)."""
    await _flag_on(ctx)
    _not_yet()


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
    """Deterministic xlsx with formulas, formula-escaped; `export_blocked` (409)."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/workbook/imports", action="workbook_import.create", response_model=ImportAcceptedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_import_route(
    return_id: UUID,
    kind: Annotated[ImportKind, Query()],
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ImportAcceptedOut:
    """Raw-body report, parsed as hostile (ADR-052); cells cited as `engine_import`."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/workbook-runs", action="workbook_run.start", response_model=WorkbookRunAcceptedOut,
    status_code=202, errors=(409, 501),
)  # fmt: skip
async def entity_start_run_route(
    return_id: UUID, body: WorkbookRunIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookRunAcceptedOut:
    """`run_in_progress` (409); a model step without consent waits on inputs (C19)."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/workbook-runs", action="workbook.read", response_model=WorkbookRunsOut, errors=(501,)
)
async def entity_runs_route(return_id: UUID, ctx: Ctx) -> WorkbookRunsOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/trial-balance", action="workbook.read", response_model=TrialBalanceOut, errors=(501,)
)
async def entity_trial_balance_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["account", "line"], Query()] = "account",
    statement: Annotated[Literal["full", "balance_sheet", "income_statement"], Query()] = "full",
    filter_: Annotated[Literal["unmapped"] | None, Query(alias="filter")] = None,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> TrialBalanceOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/trial-balance/tallies", action="workbook.read", response_model=TalliesOut,
    errors=(501,),
)  # fmt: skip
async def entity_tallies_route(return_id: UUID, ctx: Ctx) -> TalliesOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/journal-entries", action="adjusted_tb.read", response_model=JournalEntriesOut,
    errors=(501,),
)  # fmt: skip
async def entity_journal_entries_route(return_id: UUID, ctx: Ctx) -> JournalEntriesOut:
    """AJE, RJE and TJE over C8; propose and approve go through A-06's endpoints."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    "/form-lines", action="reference_set.read", response_model=FormLinesOut, errors=(501,)
)
async def entity_form_lines_route(
    ctx: Ctx,
    form: Annotated[Literal["1065", "1120-S", "1120", "990"], Query()],
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> FormLinesOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/mappings", action="account_mapping.edit", response_model=MappingProposedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_mapping_route(
    return_id: UUID, body: MappingIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MappingProposedOut:
    """A ledger mapping proposal, approved through P-04's `POST /proposals/{id}/approve`. The
    plan's `account_mapping.propose` is not in the matrix yet (A-03's file), so it is
    `account_mapping.edit`.
    """
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/schedules/k", action="workbook.read", response_model=ScheduleKOut, errors=(501,)
)
async def entity_schedule_k_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["federal", "state"], Query()] = "federal",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> ScheduleKOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/schedules/k/lines/{{line}}/breakdown", action="workbook.read",
    response_model=BreakdownOut, errors=(501,),
)  # fmt: skip
async def entity_schedule_k_breakdown_route(return_id: UUID, line: str, ctx: Ctx) -> BreakdownOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/capital-accounts", action="workbook.read", response_model=CapitalAccountsOut,
    errors=(501,),
)  # fmt: skip
async def entity_capital_accounts_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["by_partner", "by_movement"], Query()] = "by_partner",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> CapitalAccountsOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/schedules/m2", action="workbook.read", response_model=M2Out, errors=(501,)
)
async def entity_m2_route(
    return_id: UUID,
    ctx: Ctx,
    variant: Annotated[Literal["as_drafted", "with_fix"], Query()] = "as_drafted",
) -> M2Out:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/allocation-structure", action="allocation_structure.read",
    response_model=AllocationStructureOut, errors=(501,),
)  # fmt: skip
async def entity_allocation_route(
    return_id: UUID, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> AllocationStructureOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.put(
    f"{_R}/allocation-structure/draft", action="allocation_structure.edit",
    response_model=AllocationStructureOut, errors=(409, 501),
)  # fmt: skip
async def entity_allocation_draft_route(
    return_id: UUID, body: AllocationDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AllocationStructureOut:
    """A new draft version; approval is P-04's L3 sign-off on `allocation_structure`."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/allocation-structure/preview", action="allocation_structure.read",
    response_model=AllocationStructureOut, errors=(501,),
)  # fmt: skip
async def entity_allocation_preview_route(
    return_id: UUID, body: AllocationDraftIn, ctx: Ctx
) -> AllocationStructureOut:
    """Recompute without persistence."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/sections", action="workbook.read", response_model=SectionsOut, errors=(501,)
)
async def entity_sections_route(return_id: UUID, ctx: Ctx) -> SectionsOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/sections/{{key}}/sign-off", action="sign_off.create",
    response_model=SignOffRecordedOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_section_sign_off_route(
    return_id: UUID, key: str, body: SectionSignOffIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SignOffRecordedOut:
    """Tie-out precheck (`tie_out_off`, 409), then P-04's sign-off (`level_not_permitted`, 403;
    `not_preparer_of_target`)."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/issues", action="issue.read", response_model=ReturnIssuesOut, errors=(501,)
)
async def entity_issues_route(
    return_id: UUID,
    ctx: Ctx,
    section: Annotated[str | None, Query(max_length=40)] = None,
    status: Annotated[str | None, Query(max_length=40)] = None,
    step: Annotated[str | None, Query(max_length=60)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    show_resolved: Annotated[bool, Query()] = False,
) -> ReturnIssuesOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(f"{_R}/memo", action="tax_memo.read", response_model=MemoOut, errors=(501,))
async def entity_memo_route(return_id: UUID, ctx: Ctx) -> MemoOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/memo/draft", action="tax_memo.draft", response_model=AcceptedOut, status_code=202,
    errors=(409, 501),
)  # fmt: skip
async def entity_memo_draft_route(
    return_id: UUID, body: MemoDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """A memo run; `consent_required` (409) without both §7216 consents."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.patch(
    f"{_R}/memo/sections/{{key}}", action="tax_memo.edit", response_model=MemoSectionOut,
    errors=(409, 501),
)  # fmt: skip
async def entity_memo_section_route(
    return_id: UUID, key: str, body: MemoSectionEditIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MemoSectionOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/memo/adopt", action="sign_off.create", response_model=SignOffRecordedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_memo_adopt_route(
    return_id: UUID, body: MemoAdoptIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SignOffRecordedOut:
    """The preparer's L1 sign-off on the memo (`seen_hash`); the reviewer's L2 is P-04's."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/opportunities", action="tax_memo.read", response_model=OpportunitiesOut, errors=(501,)
)
async def entity_opportunities_route(return_id: UUID, ctx: Ctx) -> OpportunitiesOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/reconciliation", action="tax_reconciliation.read", response_model=ReconciliationOut,
    errors=(501,),
)  # fmt: skip
async def entity_reconciliation_route(
    return_id: UUID, ctx: Ctx, checkpoint: Annotated[UUID | None, Query()] = None
) -> ReconciliationOut:
    await _flag_on(ctx)
    _not_yet()


__all__ = ["workbook_router"]
