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
from typing import Annotated, Literal, NoReturn, cast, get_args
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ENTITY_WORKSPACE
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
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


class WorkbookOut(BaseModel):
    model_config = _cfg()

    return_id: Annotated[UUID, Internal]
    version: Annotated[int, Internal]
    sheets: Annotated[list[WorkbookSheetOut], Internal]
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class WorkbookCellOut(BaseModel):
    model_config = _cfg()

    address: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[0-9]{1,6}$"), Internal]
    value: Annotated[str | None, Tri] = None  # exact decimal or text, as stored
    formula: Annotated[str | None, Tri] = None  # E13's closed grammar (ADR-237)
    author: Annotated[CellAuthor, Internal]
    state: Annotated[CellState, Internal]
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    version: Annotated[int, Internal]


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


class WorkbookTrialBalanceOut(BaseModel):
    model_config = _cfg()

    view: Annotated[Literal["account", "line"], Internal]
    rows: Annotated[list[WorkbookTbRowOut], Tri]
    unmapped: Annotated[int, Field(ge=0), Internal]


class WorkbookTallyOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    state: Annotated[TallyState, Internal]
    difference: Annotated[MaybeMoney, Tri] = None


class WorkbookTalliesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookTallyOut], Tri]


class WorkbookJournalEntryOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    kind: Annotated[Literal["aje", "rje", "tje"], Internal]
    reference: Annotated[str, Internal]  # "TJE-3"
    amount: Annotated[Decimal, Tri]
    state: Annotated[str, Internal]


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
    model_config = _cfg()

    proposal_id: Annotated[UUID, Internal]


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


class WorkbookCapitalTotalsOut(BaseModel):
    """T-05-T34: the server's column totals (the screen never sums)."""

    model_config = _cfg()

    beginning: Annotated[Decimal, Tri]
    contributions: Annotated[Decimal, Tri]
    income: Annotated[Decimal, Tri]
    distributions: Annotated[Decimal, Tri]
    ending: Annotated[Decimal, Tri]


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
    lines: Annotated[list[WorkbookM2LineOut], Tri] = Field(default_factory=list)
    item_l: Annotated[WorkbookItemLOut | None, Tri] = None


# --- the allocation structure ------------------------------------------------------------------


class WorkbookRungOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    amount: Annotated[MaybeMoney, Tri] = None
    percentage: Annotated[Decimal | None, Tri] = None
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class WorkbookAllocationStructureOut(BaseModel):
    model_config = _cfg()

    version: Annotated[int, Internal]
    kind: Annotated[StructureKind, Internal]
    status: Annotated[StructureStatus, Internal]
    rungs: Annotated[list[WorkbookRungOut], Tri]
    seen_hash: Annotated[str, Internal]  # what an L3 sign-off names (P-04)
    allowed_actions: Annotated[list[WorkbookAction], Internal]


class WorkbookAllocationDraftIn(BaseModel):
    model_config = _cfg()

    expected_version: Annotated[int, Internal]
    kind: Annotated[StructureKind, Internal]
    rungs: Annotated[list[WorkbookRungOut], Field(min_length=1, max_length=20), Tri]


# --- sections, issues, the memo, reconciliation ------------------------------------------------


class WorkbookSectionOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Internal]
    title: Annotated[str, Internal]
    tallies: Annotated[list[WorkbookTallyOut], Tri]
    signed_levels: Annotated[list[str], Internal]


class WorkbookSectionsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookSectionOut], Tri]


class WorkbookSectionSignOffIn(BaseModel):
    model_config = _cfg()

    level: Annotated[Literal["l2", "l3"], Internal]
    seen_hash: Annotated[str, Internal]
    note: Annotated[str | None, Field(max_length=500), Confidential] = None


class WorkbookSignOffRecordedOut(BaseModel):
    model_config = _cfg()

    sign_off_id: Annotated[UUID, Internal]


class WorkbookReturnIssueOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    section: Annotated[str | None, Internal] = None
    step: Annotated[str | None, Internal] = None
    status: Annotated[str, Internal]


class WorkbookReturnIssuesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[WorkbookReturnIssueOut], Confidential]
    by_section: Annotated[dict[str, int], Internal]
    by_step: Annotated[dict[str, int], Internal]


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


class WorkbookReconciliationOut(BaseModel):
    model_config = _cfg()

    checkpoint_id: Annotated[UUID | None, Internal] = None
    rows: Annotated[list[WorkbookReconciliationRowOut], Tri]
    differences: Annotated[int, Field(ge=0), Internal]


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


class RunInProgress(DomainConflict):
    """A workbook run of this return is still open: one at a time (TXP-00)."""

    code = "run_in_progress"


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@workbook_router.get(
    f"{_R}/general-information", action="tax_return.read",
    response_model=WorkbookGeneralInformationOut, errors=(501,),
)  # fmt: skip
async def entity_general_information_route(
    return_id: UUID, ctx: Ctx
) -> WorkbookGeneralInformationOut:
    await _flag_on(ctx)
    # The answer carries EIN and TIN last fours (Restricted, pii_kind tin): masked for an
    # offshore reader once the stub answers (review 6; S35 round 2 end pass).
    return await mask_tins_for(ctx, _not_yet())


@workbook_router.get(
    f"{_R}/partners", action="tax_return.read", response_model=WorkbookPartnersOut, errors=(501,)
)
async def entity_partners_route(return_id: UUID, ctx: Ctx) -> WorkbookPartnersOut:
    await _flag_on(ctx)
    # The answer carries EIN and TIN last fours (Restricted, pii_kind tin): masked for an
    # offshore reader once the stub answers (review 6; S35 round 2 end pass).
    return await mask_tins_for(ctx, _not_yet())


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
    return WorkbookOut(
        return_id=return_id,
        version=1,
        sheets=[WorkbookSheetOut(key=n, title=t) for n, t in sheets_of(form)],
        allowed_actions=[cast(WorkbookAction, a) for a in get_args(WorkbookAction) if a in held],
    )


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
    """One sheet with range paging (T-05-T27): values and formulas, never evaluated text."""
    del version  # one live version until the workbook run versions it (T-05-T32)
    await _flag_on(ctx)
    form, _resource = await _workbook_read(ctx, return_id)
    from abacus.modules.review.api import current_values
    from abacus.modules.tax.workbook_service import WORKBOOK, sheet_cells, sheet_or_404

    values = await current_values(ctx.tenant, WORKBOOK, return_id)
    cells, next_range = sheet_cells(values, sheet_or_404(form, sheet), range_)
    return WorkbookSheetCellsOut(
        sheet=sheet,
        version=1,
        cells=[
            WorkbookCellOut(
                address=c.address,
                value=c.value,
                formula=c.formula,
                author="formula" if c.formula else "person",
                state="formula" if c.formula else "value",
                version=1,
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
    errors=(409, 501),
)  # fmt: skip
async def entity_edit_cell_route(
    return_id: UUID,
    address: str,
    body: WorkbookCellEditIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookCellOut:
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
    f"{_R}/workbook/imports", action="workbook_import.create",
    response_model=WorkbookImportAcceptedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_import_route(
    return_id: UUID,
    kind: Annotated[ImportKind, Query()],
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookImportAcceptedOut:
    """Raw-body report, parsed as hostile (ADR-052); cells cited as `engine_import`."""
    await _flag_on(ctx)
    _not_yet()


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
    await authorise(ctx, "workbook_run.start", await return_resource(ctx, loaded))
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
    return WorkbookTrialBalanceOut(
        view=view,
        rows=[WorkbookTbRowOut(**r.__dict__) for r in rows],
        unmapped=unmapped,
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
    found = await tb_tallies(ctx, return_id, loaded.facts.engagement_id)
    return WorkbookTalliesOut(
        items=[
            WorkbookTallyOut(key=t.key, label=t.label, state=t.state, difference=t.difference)
            for t in found
        ]
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
            WorkbookJournalEntryOut(id=i, kind=k, reference=ref, amount=amount, state=state)  # type: ignore[arg-type]  # C8's kinds
            for i, k, ref, amount, state in await journal_entries(ctx, return_id)
            if k in ("aje", "rje", "tje")
        ]
    )


@workbook_router.get(
    "/form-lines", action="reference_set.read", response_model=WorkbookFormLinesOut, errors=(501,)
)
async def entity_form_lines_route(
    ctx: Ctx,
    form: Annotated[Literal["1065", "1120-S", "1120", "990"], Query()],
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> WorkbookFormLinesOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/mappings", action="account_mapping.edit", response_model=WorkbookMappingProposedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_mapping_route(
    return_id: UUID, body: WorkbookMappingIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookMappingProposedOut:
    """A ledger mapping proposal, approved through P-04's `POST /proposals/{id}/approve`. The
    plan's `account_mapping.propose` is not in the matrix yet (A-03's file), so it is
    `account_mapping.edit`.
    """
    await _flag_on(ctx)
    _not_yet()


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
    return WorkbookScheduleKOut(
        view=view,
        lines=[
            WorkbookScheduleKLineOut(
                line=k.line,
                label=k.label,
                total=k.total,
                by_partner=[
                    WorkbookScheduleKCellOut(partner_id=p, amount=a) for p, a in k.by_partner
                ],
                tie=k.tie,
            )
            for k in es.schedule_k(values, partners, view)
        ],
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
            )
            for r in rows
        ],
        tie=es.capital_tie(rows),
        totals=WorkbookCapitalTotalsOut(**totals.__dict__),
        item_l=WorkbookItemLOut(**found.__dict__),
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


@workbook_router.get(
    f"{_R}/allocation-structure", action="allocation_structure.read",
    response_model=WorkbookAllocationStructureOut, errors=(501,),
)  # fmt: skip
async def entity_allocation_route(
    return_id: UUID, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> WorkbookAllocationStructureOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.put(
    f"{_R}/allocation-structure/draft", action="allocation_structure.edit",
    response_model=WorkbookAllocationStructureOut, errors=(409, 501),
)  # fmt: skip
async def entity_allocation_draft_route(
    return_id: UUID, body: WorkbookAllocationDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookAllocationStructureOut:
    """A new draft version; approval is P-04's L3 sign-off on `allocation_structure`."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/allocation-structure/preview", action="allocation_structure.read",
    response_model=WorkbookAllocationStructureOut, errors=(501,),
)  # fmt: skip
async def entity_allocation_preview_route(
    return_id: UUID, body: WorkbookAllocationDraftIn, ctx: Ctx
) -> WorkbookAllocationStructureOut:
    """Recompute without persistence."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/sections", action="workbook.read", response_model=WorkbookSectionsOut, errors=(501,)
)
async def entity_sections_route(return_id: UUID, ctx: Ctx) -> WorkbookSectionsOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/sections/{{key}}/sign-off", action="sign_off.create",
    response_model=WorkbookSignOffRecordedOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_section_sign_off_route(
    return_id: UUID,
    key: str,
    body: WorkbookSectionSignOffIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkbookSignOffRecordedOut:
    """Tie-out precheck (`tie_out_off`, 409), then P-04's sign-off (`level_not_permitted`, 403;
    `not_preparer_of_target`)."""
    await _flag_on(ctx)
    _not_yet()


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
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/memo", action="tax_memo.read", response_model=WorkbookMemoOut, errors=(501,)
)
async def entity_memo_route(return_id: UUID, ctx: Ctx) -> WorkbookMemoOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/memo/draft", action="tax_memo.draft",
    response_model=WorkbookAcceptedOut, status_code=202,
    errors=(409, 501),
)  # fmt: skip
async def entity_memo_draft_route(
    return_id: UUID, body: WorkbookMemoDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookAcceptedOut:
    """A memo run; `consent_required` (409) without both §7216 consents."""
    await _flag_on(ctx)
    _not_yet()


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
    await _flag_on(ctx)
    _not_yet()


@workbook_router.post(
    f"{_R}/memo/adopt", action="sign_off.create", response_model=WorkbookSignOffRecordedOut,
    status_code=201, errors=(409, 501),
)  # fmt: skip
async def entity_memo_adopt_route(
    return_id: UUID, body: WorkbookMemoAdoptIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WorkbookSignOffRecordedOut:
    """The preparer's L1 sign-off on the memo (`seen_hash`); the reviewer's L2 is P-04's."""
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/opportunities",
    action="tax_memo.read",
    response_model=WorkbookOpportunitiesOut,
    errors=(501,),
)
async def entity_opportunities_route(return_id: UUID, ctx: Ctx) -> WorkbookOpportunitiesOut:
    await _flag_on(ctx)
    _not_yet()


@workbook_router.get(
    f"{_R}/reconciliation", action="tax_reconciliation.read",
    response_model=WorkbookReconciliationOut,
    errors=(501,),
)  # fmt: skip
async def entity_reconciliation_route(
    return_id: UUID, ctx: Ctx, checkpoint: Annotated[UUID | None, Query()] = None
) -> WorkbookReconciliationOut:
    await _flag_on(ctx)
    _not_yet()


__all__ = ["workbook_router"]
