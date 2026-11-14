"""The closes contract, stub PR 2: intake, accounts, reconciliation, review, flux and the portal
questions (C-01-T05; C-01 §4.3; SPEC-655 F3, F6 to F9; `docs/contracts/closes.md` §5 to §9).
Screens CLS-03, CLS-04, CLS-05, CLS-06, CLS-10 and POR-11.

Firm routes answer as part 1 does (`contract.py`): a client principal 404, `closes.engine` off
404, a human-only route refuses non-persons 403, then 501. A transaction question to a client
also needs `closes.portal_requests`. The two portal routes answer only a client principal (a firm
member 404), need `closes.portal_requests`, read inside the grant (`scope_only`, INV-4) and carry
only client-shaped fields: never the issue, its severity or the agent (QC-9, AC-47).

Classification (ADR-031): ledger amounts, register lines, statement lines, client answers and
explanations are client financial content, `confidential`; client answers are sealed at rest.
Money is `Decimal`, two places, computed by code (ADR-050); model text only cites fact tokens.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CLOSES_ENGINE, CLOSES_PORTAL_REQUESTS
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.closes.contract import ClosePersonOut, PlannedLinkOut
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=64)]
Internal = classified("internal")
Confidential = classified("confidential")
Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2), Confidential]
MaybeMoney = Annotated[Decimal | None, Field(max_digits=18, decimal_places=2), Confidential]
AccountRef = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]

TallyWord = Literal["pending", "tie", "off", "ties_once_posted", "recorded", "reconciled"]
IncorporationWord = Literal["pending", "incorporated", "returned"]
ItemKind = Literal[
    "deposit_in_transit",
    "outstanding_check",
    "unrecorded_deposit",
    "unrecorded_withdrawal",
    "bank_error",
    "book_error",
]
Classification = Literal["asset", "liability", "equity", "income", "expense"]
FluxBasis = Literal["mom", "yoy", "budget"]
FluxTest = Literal["within", "over_both", "not_comparable"]
FluxLineStatus = Literal[
    "within_threshold", "unexplained", "explained_draft", "explained", "accepted"
]
QuestionStatus = Literal["open", "answered", "withdrawn"]
Severity = Literal["high", "medium", "low"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- refusal codes -------------------------------------------------------------------------------


class OpenItems(DomainConflict):
    """L1 sign-off on a reconciliation with open items (AC-42)."""

    code = "open_items"


class StatementNotAvailable(DomainConflict):
    """The statement is still requested (CLS-05 g; AC-43)."""

    code = "statement_not_available"


class QuestionTemplateRequired(DomainConflict):
    """A transaction question needs the firm's DB template (DV-7; template wording only)."""

    code = "question_template_required"


# --- CLS-03 intake -------------------------------------------------------------------------------


class RequestNodeOut(BaseModel):
    """One node of the intake tree: a category or a request with its counts (CLS-03)."""

    model_config = _cfg()

    node_id: Annotated[str, Field(min_length=1, max_length=80), Internal]
    kind: Annotated[Literal["category", "request"], Internal]
    title: Annotated[str, Confidential]
    request_item_id: Annotated[UUID | None, Internal] = None
    status: Annotated[str | None, Internal] = None  # `request_close` / `close_incorporation`
    received: Annotated[int, Field(ge=0), Internal] = 0
    total: Annotated[int, Field(ge=0), Internal] = 0
    client_visible: Annotated[bool, Internal] = True  # bank-feed requests are internal (QC-1)
    linked: Annotated[int, Field(ge=0), Internal] = 0  # "Linked (n)", the C5 fulfilment count
    screening: Annotated[Literal["clear", "partly", "flagged", "running"] | None, Internal] = None
    overdue: Annotated[bool, Internal] = False
    children: list[RequestNodeOut] = []


class RequestTreeOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Internal]
    published: Annotated[bool, Internal]
    publishes_on: Annotated[date | None, Internal] = None  # "Requests publish Oct 1 (BD1)…"
    plan_version: Annotated[int | None, Field(ge=1), Internal] = None
    marked_done_by: Annotated[str | None, Confidential] = None  # "Marked done by Ben Ashby"
    nodes: list[RequestNodeOut]


class QuestionnaireAnswerOut(BaseModel):
    model_config = _cfg()

    question: Annotated[str, Confidential]
    answer: Annotated[str | None, Confidential] = None
    answered_by: Annotated[str | None, Confidential] = None


class CloseQuestionnaireOut(BaseModel):
    """CLS-03 d: 5 questions, 4 answered by Ben Ashby."""

    model_config = _cfg()

    answered: Annotated[int, Field(ge=0), Internal]
    total: Annotated[int, Field(ge=0), Internal]
    items: list[QuestionnaireAnswerOut]


class CitedFigureOut(BaseModel):
    """A code-computed figure with its `sheet_cell` citation (INV-2)."""

    model_config = _cfg()

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$"), Internal]
    label: Annotated[str, Confidential]
    amount: MaybeMoney = None
    count: Annotated[int | None, Field(ge=0), Internal] = None  # "5,143 transactions"
    citation_id: Annotated[UUID, Internal]


class IntakeSummaryOut(BaseModel):
    """The intake summary card (CLS-03 a, a2): totals are code; the paragraph is `close.agent`
    mode `intake` text over fact tokens, or "Totals from the file" with the agent off (DV-3)."""

    model_config = _cfg()

    evidence_version_id: Annotated[UUID, Internal]
    label: Annotated[Literal["summarized_by_agent", "totals_from_file"], Internal]
    figures: list[CitedFigureOut]
    paragraph: Annotated[str | None, Confidential] = None
    run_id: Annotated[UUID | None, Internal] = None


# --- CLS-04 accounts and schedules ---------------------------------------------------------------


class AccountNodeOut(BaseModel):
    """Classification, then account type, then leaf; balances roll up in code; contra balances
    render in parentheses (AC-35)."""

    model_config = _cfg()

    node_id: Annotated[str, Field(min_length=1, max_length=80), Internal]
    kind: Annotated[Literal["classification", "account_type", "account"], Internal]
    name: Annotated[str, Confidential]
    account_external_id: Annotated[str | None, Internal] = None
    number: Annotated[str | None, Confidential] = None
    mask: Annotated[str | None, Field(pattern=r"^••[0-9]{4}$"), Internal] = None
    classification: Annotated[Classification, Internal]
    is_contra: Annotated[bool, Internal] = False
    balance: Money
    tally: Annotated[TallyWord | None, Internal] = None
    off_by: MaybeMoney = None
    children: list[AccountNodeOut] = []


class AccountTreeOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Internal]
    snapshot_id: Annotated[UUID, Internal]
    synced_at: Annotated[datetime | None, Internal] = None
    totals: Annotated[dict[Classification, Decimal], Confidential]
    nodes: list[AccountNodeOut]


class RegisterLineOut(BaseModel):
    """One register row, citable as a `ledger_line` (CLS-04 e)."""

    model_config = _cfg()

    line_ref: Annotated[str, Field(min_length=1, max_length=120), Internal]
    txn_date: Annotated[date, Internal]
    txn_type: Annotated[str | None, Confidential] = None
    category: Annotated[str | None, Confidential] = None  # the offset account
    payee: Annotated[str | None, Confidential] = None
    memo: Annotated[str | None, Confidential] = None
    amount: Money
    citation_id: Annotated[UUID | None, Internal] = None


class CloseRegisterOut(BaseModel):
    model_config = _cfg()

    account_external_id: Annotated[str, Internal]
    items: list[RegisterLineOut]
    next_cursor: Annotated[str | None, Internal] = None


class ScheduleLineOut(BaseModel):
    model_config = _cfg()

    period: Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"), Internal]
    inflows: Money
    aje: Money
    ending_balance: Money


class ArrangementOut(BaseModel):
    """A prepaid, fixed asset, accrual or deferred revenue (CLS-04 a2); each edit a version."""

    model_config = _cfg()

    arrangement_id: Annotated[UUID, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    kind: Annotated[Literal["prepaid", "fixed_asset", "accrual", "deferred_revenue"], Internal]
    description: Annotated[str, Confidential]
    expense_account_ref: Annotated[str, Internal]
    scheduled_total: Money
    frequency: Annotated[Literal["monthly", "quarterly", "annual"], Internal]
    start_on: Annotated[date, Internal]
    finish_on: Annotated[date, Internal]
    source_citation_id: Annotated[UUID | None, Internal] = None


class EntryRecordingOut(BaseModel):
    """ "Recorded in QuickBooks · JE 48214 · found by sync 10:20" (c-prime; DV-1)."""

    model_config = _cfg()

    proposed_entry_id: Annotated[UUID, Internal]
    entry_number: Annotated[str, Confidential]  # "AJE-02"
    external_txn_id: Annotated[str, Internal]  # "48214"
    found_at: Annotated[datetime, Internal]
    confirmed_by: ClosePersonOut | None = None


class CloseWorkpaperOut(BaseModel):
    """CLS-04 a/b/d: the schedule against the GL; read-only: no Post control (DV-1)."""

    model_config = _cfg()

    account_external_id: Annotated[str, Internal]
    account_name: Annotated[str, Confidential]
    gl_balance: Money
    schedule_balance: Money
    tally: Annotated[TallyWord, Internal]
    off_by: MaybeMoney = None
    pending_entry_number: Annotated[str | None, Confidential] = None
    approval: Annotated[str | None, Confidential] = None  # "Approved by RM under BH AJE …"
    note: Annotated[str | None, Confidential] = None  # "Record it in QuickBooks; …"
    recording: EntryRecordingOut | None = None
    arrangements: list[ArrangementOut]
    lines: list[ScheduleLineOut]
    review_issue_id: Annotated[UUID | None, Internal] = None


class ArrangementIn(BaseModel):
    model_config = _cfg()

    kind: Annotated[Literal["prepaid", "fixed_asset", "accrual", "deferred_revenue"], Internal]
    description: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    expense_account_ref: Annotated[str, Field(min_length=1, max_length=64), Internal]
    scheduled_total: Money
    frequency: Annotated[Literal["monthly", "quarterly", "annual"], Internal] = "monthly"
    start_on: Annotated[date, Internal]
    finish_on: Annotated[date, Internal]
    source_citation_id: Annotated[UUID | None, Internal] = None


class RecategorizationIn(BaseModel):
    """A register row's new category: a reclass proposal to SHL-10, never a change to the
    transaction (AC-36)."""

    model_config = _cfg()

    to_account_ref: Annotated[str, Field(min_length=1, max_length=64), Internal]
    note: Annotated[str | None, Field(max_length=500), Confidential] = None


class ProposalRefOut(BaseModel):
    model_config = _cfg()

    proposed_entry_id: Annotated[UUID, Internal]
    entry_number: Annotated[str, Confidential]
    review_href: Annotated[str, Internal]  # SHL-10 `?ov=approve:<proposalId>` until CLS-07


# --- CLS-05 reconciliation -----------------------------------------------------------------------


class StatementRegionOut(BaseModel):
    """A statement region: page and cell box, verified as `document_text` before display."""

    model_config = _cfg()

    page_no: Annotated[int, Field(ge=1), Internal]
    bbox: Annotated[list[float], Field(min_length=4, max_length=4), Internal]
    citation_id: Annotated[UUID, Internal]


class ReconcilingItemOut(BaseModel):
    model_config = _cfg()

    item_id: Annotated[UUID, Internal]
    side: Annotated[Literal["bank", "book"], Internal]
    kind: Annotated[ItemKind, Internal]
    ref: Annotated[str | None, Confidential] = None  # "#2281"
    txn_date: Annotated[date, Internal]
    days_at_period_end: Annotated[int, Field(ge=0), Internal]
    amount: Money
    stale: Annotated[bool, Internal] = False  # "Stale > 90 days"
    region: StatementRegionOut | None = None
    register_line_ref: Annotated[str | None, Internal] = None
    issue_id: Annotated[UUID | None, Internal] = None
    proposed_entry_id: Annotated[UUID | None, Internal] = None
    resolution: Annotated[Literal["carry_forward", "cleared"] | None, Internal] = None


class CloseStatementLineOut(BaseModel):
    model_config = _cfg()

    statement_line_id: Annotated[UUID, Internal]
    txn_date: Annotated[date, Internal]
    description: Annotated[str, Confidential]
    withdrawal: MaybeMoney = None
    deposit: MaybeMoney = None
    region: StatementRegionOut
    matched: Annotated[bool, Internal]
    low_confidence: Annotated[bool, Internal] = False  # outlined; never auto-matched (AC-40)


class CloseReconciliationOut(BaseModel):
    """Both sides to the cent (AC-39): balance per bank + deposits in transit - outstanding
    checks = adjusted bank; book + unrecorded = adjusted book; difference."""

    model_config = _cfg()

    reconciliation_id: Annotated[UUID, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    account_external_id: Annotated[str, Internal]
    account_name: Annotated[str, Confidential]
    period_end: Annotated[date, Internal]
    statement_evidence_version_id: Annotated[UUID | None, Internal] = None
    statement_requested_on: Annotated[date | None, Internal] = None  # CLS-05 g
    balance_per_bank: MaybeMoney = None
    adjusted_bank: MaybeMoney = None
    book_balance: Money
    adjusted_book: Money
    difference: MaybeMoney = None
    tally: Annotated[TallyWord, Internal]
    items: list[ReconcilingItemOut]
    statement_lines: list[CloseStatementLineOut]
    signed_off_by: ClosePersonOut | None = None
    sign_off_stale: Annotated[bool, Internal] = False
    sign_off_blockers: Annotated[list[str], Internal] = []
    engine_version: Annotated[str, Internal]
    inputs_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]


class ResolveItemIn(BaseModel):
    model_config = _cfg()

    resolution: Annotated[Literal["carry_forward", "cleared"], Internal]
    note: Annotated[str, Field(min_length=1, max_length=1000), Confidential]


class EntryLineOut(BaseModel):
    model_config = _cfg()

    account_ref: Annotated[str, Internal]
    account_name: Annotated[str, Confidential]
    debit: MaybeMoney = None
    credit: MaybeMoney = None


class EntryDraftOut(BaseModel):
    """The agent's AJE draft, a suggestion (CLS-05 a2): amount and debit account are code; the
    reasoning is mode `aje` text over facts; a person proposes (AC-41)."""

    model_config = _cfg()

    suggestion_id: Annotated[UUID | None, Internal] = None
    lines: list[EntryLineOut]
    reasoning: Annotated[str | None, Confidential] = None
    citation_ids: Annotated[list[UUID], Internal] = []
    drafted_by: Annotated[Literal["agent", "code"], Internal]


class EntryProposalIn(BaseModel):
    model_config = _cfg()

    reconciliation_item_id: Annotated[UUID | None, Internal] = None
    description: Annotated[str, Field(min_length=1, max_length=500), Confidential]
    lines: Annotated[list[EntryLineOut], Field(min_length=2, max_length=50)]


# --- CLS-06 review and transaction questions -----------------------------------------------------


class CloseIssueOut(BaseModel):
    model_config = _cfg()

    issue_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    severity: Annotated[Severity, Internal]
    issue_class: Annotated[
        Literal["bank_rec", "schedule", "flux", "recategorize", "intake"], Internal
    ]
    status: Annotated[str, Internal]  # P-04's issue words
    waiting_on_client: Annotated[bool, Internal] = False
    why_surfaced: Annotated[str | None, Confidential] = None  # mode `bank_rec` or a template
    account_external_id: Annotated[str | None, Internal] = None
    register_line_ref: Annotated[str | None, Internal] = None
    question_id: Annotated[UUID | None, Internal] = None
    resolved_by: ClosePersonOut | None = None


class CloseIssuesOut(BaseModel):
    """Medium 2 + Low 5 = 7 = the Review badge = CLS-02's Open Issues; notes never count."""

    model_config = _cfg()

    open: Annotated[int, Field(ge=0), Internal]
    by_severity: Annotated[dict[Severity, int], Internal]
    notes: Annotated[int, Field(ge=0), Internal]
    items: list[CloseIssueOut]
    adjustments: PlannedLinkOut | None = None  # CLS-07 (C-02), planned


class TransactionQuestionIn(BaseModel):
    """The firm's DB template with code-filled facts; the person may edit before Send (DV-7)."""

    model_config = _cfg()

    template_id: Annotated[UUID, Internal]
    template_version: Annotated[int, Field(ge=1), Internal]
    client_wording: Annotated[str, Field(min_length=1, max_length=2000), Confidential]
    assignee_contact_id: Annotated[UUID, Internal]


class TransactionQuestionOut(BaseModel):
    model_config = _cfg()

    question_id: Annotated[UUID, Internal]
    issue_id: Annotated[UUID | None, Internal] = None
    status: Annotated[QuestionStatus, Internal]
    asked_by: ClosePersonOut
    asked_at: Annotated[datetime, Internal]
    answered_at: Annotated[datetime | None, Internal] = None


# --- CLS-10 flux ---------------------------------------------------------------------------------


class FluxDriverOut(BaseModel):
    """A driver foots to the change in code or the run repairs once, then asks (AC-49)."""

    model_config = _cfg()

    label: Annotated[str, Confidential]
    amount: Money
    citation_id: Annotated[UUID, Internal]


class FluxLineOut(BaseModel):
    model_config = _cfg()

    line_id: Annotated[UUID, Internal]
    line_key: Annotated[str, Internal]
    caption: Annotated[str, Confidential]
    prior: MaybeMoney = None  # "—" when the prior period is not in the ledger
    current: Money
    change: MaybeMoney = None
    change_pct: Annotated[Decimal | None, Field(max_digits=9, decimal_places=1), Internal] = None
    test: Annotated[FluxTest, Internal]
    status: Annotated[FluxLineStatus, Internal]
    explanation: Annotated[str | None, Confidential] = None
    drivers: list[FluxDriverOut] = []
    accepted_by: ClosePersonOut | None = None
    row_version: Annotated[int, Field(ge=1), Internal] = 1


class FluxSetOut(BaseModel):
    model_config = _cfg()

    set_id: Annotated[UUID, Internal]
    basis: Annotated[FluxBasis, Internal]
    threshold_label: Annotated[str, Confidential]  # "10% and $2,500" (KNW-04)
    tested: Annotated[int, Field(ge=0), Internal]
    explained: Annotated[int, Field(ge=0), Internal]
    unexplained: Annotated[int, Field(ge=0), Internal]
    budget_available: Annotated[bool, Internal] = False  # "No budget on file"
    lines: list[FluxLineOut]
    engine_version: Annotated[str, Internal]


class FluxExplanationIn(BaseModel):
    model_config = _cfg()

    text: Annotated[str, Field(min_length=1, max_length=2000), Confidential]


class StartedRunOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]


# --- POR-11 portal questions (client-shaped only, QC-9) ------------------------------------------


class PortalQuestionOut(BaseModel):
    """What the client sees: the client wording and its context line, never the issue, its
    severity or the agent (AC-47, INV-4)."""

    model_config = _cfg()

    question_id: Annotated[UUID, Internal]
    client_wording: Annotated[str, Confidential]
    context_line: Annotated[str, Confidential]  # "Front Range Bank ••4410 · check #2285 · …"
    status: Annotated[QuestionStatus, Internal]
    asked_by_name: Annotated[str, Confidential]
    asked_at: Annotated[datetime, Internal]
    answered_at: Annotated[datetime | None, Internal] = None


class PortalQuestionsOut(BaseModel):
    model_config = _cfg()

    items: list[PortalQuestionOut]


class PortalAnswerIn(BaseModel):
    model_config = _cfg()

    choice: Annotated[Literal["lost_reissue", "voided", "something_else"] | None, Internal] = None
    note: Annotated[str | None, Field(max_length=2000), Confidential] = None
    attachment_upload_id: Annotated[UUID | None, Internal] = None


# --- routes (each 501, one action) ---------------------------------------------------------------

close_work_router = AbacusRouter(prefix="/v1", tags=["closes"])
portal_close_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])
_C = "/closes/{close_id}"


async def _engine_on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, CLOSES_ENGINE):
        raise NotFound(CLOSES_ENGINE.name)


async def _human_route(ctx: AuthContext, action: str) -> None:
    await _engine_on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _portal_on(ctx: AuthContext) -> None:
    """Only a client principal reaches a portal question; the flag off answers 404."""
    if not ctx.client or not await flag_enabled(ctx.tenant, CLOSES_PORTAL_REQUESTS):
        raise NotFound(CLOSES_PORTAL_REQUESTS.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@close_work_router.get(
    f"{_C}/requests", action="close.read", response_model=RequestTreeOut, errors=(501,)
)
async def close_requests_route(
    close_id: UUID,
    ctx: Ctx,
    view: Annotated[Literal["tree"], Query()] = "tree",
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    status: Annotated[str | None, Query(pattern=r"^[a-z_]{1,40}$")] = None,
) -> RequestTreeOut:
    """CLS-03's tree with counts, screening glyph and Linked (n) (C-01-T19)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(
    f"{_C}/questionnaire", action="close.read", response_model=CloseQuestionnaireOut,
    errors=(501,),
)  # fmt: skip
async def close_questionnaire_route(close_id: UUID, ctx: Ctx) -> CloseQuestionnaireOut:
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(
    "/evidence-versions/{evidence_version_id}/close-summary",
    action="close.read",
    response_model=IntakeSummaryOut,
    errors=(501,),
)
async def close_intake_summary_route(evidence_version_id: UUID, ctx: Ctx) -> IntakeSummaryOut:
    """Code totals with `sheet_cell` citations and the mode `intake` paragraph (C-01-T19)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(
    f"{_C}/accounts", action="close.read", response_model=AccountTreeOut, errors=(501,)
)
async def close_accounts_route(
    close_id: UUID,
    ctx: Ctx,
    show_zero: Annotated[bool, Query()] = False,
    group_by: Annotated[Literal["classification", "procedure"], Query()] = "classification",
) -> AccountTreeOut:
    """CLS-04's tree (C-01-T21)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(
    f"{_C}/accounts/{{account_ref}}/register",
    action="close.read",
    response_model=CloseRegisterOut,
    errors=(501,),
)
async def close_register_route(
    close_id: UUID,
    account_ref: AccountRef,
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> CloseRegisterOut:
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(
    f"{_C}/accounts/{{account_ref}}/workpaper",
    action="close.read",
    response_model=CloseWorkpaperOut,
    errors=(501,),
)
async def close_workpaper_route(
    close_id: UUID, account_ref: AccountRef, ctx: Ctx
) -> CloseWorkpaperOut:
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(
    f"{_C}/accounts/{{account_ref}}/workpaper.xlsx", action="close.read", response_model=bytes,
    errors=(501,),
)  # fmt: skip
async def close_workpaper_xlsx_route(
    close_id: UUID, account_ref: AccountRef, ctx: Ctx
) -> Response:
    """The workpaper as Excel, formula-escaped (C-01-T21)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.post(
    f"{_C}/accounts/{{account_ref}}/arrangements",
    action="arrangement.edit",
    response_model=ArrangementOut,
    status_code=201,
    errors=(409, 501),
)
async def create_arrangement_route(
    close_id: UUID, account_ref: AccountRef, body: ArrangementIn, ctx: Ctx
) -> ArrangementOut:
    """A new arrangement and its first version (AC-37; C-01-T21)."""
    await _human_route(ctx, "arrangement.edit")
    _not_yet()


@close_work_router.patch(
    "/arrangements/{arrangement_id}",
    action="arrangement.edit",
    response_model=ArrangementOut,
    errors=(409, 501),
)
async def update_arrangement_route(
    arrangement_id: UUID, body: ArrangementIn, ctx: Ctx, if_match: IfMatch
) -> ArrangementOut:
    """A new version per edit (C-01-T21)."""
    await _human_route(ctx, "arrangement.edit")
    _not_yet()


@close_work_router.post(
    "/register-lines/{line_ref}/recategorization-proposals",
    action="proposed_entry.create",
    response_model=ProposalRefOut,
    status_code=201,
    errors=(409, 501),
)
async def recategorize_route(
    line_ref: Annotated[str, Path(min_length=1, max_length=120)],
    body: RecategorizationIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ProposalRefOut:
    """A person's reclass proposal to SHL-10 (AC-36; C-01-T21)."""
    await _human_route(ctx, "proposed_entry.create")
    _not_yet()


@close_work_router.get(
    f"{_C}/reconciliations/{{account_ref}}", action="close.read",
    response_model=CloseReconciliationOut, errors=(409, 501),
)  # fmt: skip
async def close_reconciliation_route(
    close_id: UUID, account_ref: AccountRef, ctx: Ctx
) -> CloseReconciliationOut:
    """CLS-05's VM: both sides, items, aging, matches and regions (C-01-T23)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.post(
    "/reconciliations/{reconciliation_id}/items/{item_id}/resolve",
    action="reconciliation.resolve_item",
    response_model=ReconcilingItemOut,
    errors=(409, 501),
)
async def resolve_reconciling_item_route(
    reconciliation_id: UUID, item_id: UUID, body: ResolveItemIn, ctx: Ctx
) -> ReconcilingItemOut:
    """Carry forward or cleared, with a required note; a person's (C-01-T23)."""
    await _human_route(ctx, "reconciliation.resolve_item")
    _not_yet()


@close_work_router.get(
    "/reconciliations/{reconciliation_id}/items/{item_id}/entry-draft",
    action="close.read",
    response_model=EntryDraftOut,
    errors=(501,),
)
async def reconciling_item_entry_draft_route(
    reconciliation_id: UUID, item_id: UUID, ctx: Ctx
) -> EntryDraftOut:
    await _engine_on(ctx)
    _not_yet()


@close_work_router.post(
    f"{_C}/entries",
    action="proposed_entry.create",
    response_model=ProposalRefOut,
    status_code=201,
    errors=(409, 501),
)
async def propose_close_entry_route(
    close_id: UUID, body: EntryProposalIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ProposalRefOut:
    """A person proposes through `adjustments.api.propose_entry`; the agent cannot (AC-41)."""
    await _human_route(ctx, "proposed_entry.create")
    _not_yet()


@close_work_router.get(
    f"{_C}/issues", action="close.read", response_model=CloseIssuesOut, errors=(501,)
)
async def close_issues_route(
    close_id: UUID,
    ctx: Ctx,
    issue_class: Annotated[str | None, Query(alias="class", pattern=r"^[a-z_]{1,40}$")] = None,
    include_resolved: Annotated[bool, Query()] = False,
) -> CloseIssuesOut:
    """CLS-06's queue facets and badge (C-01-T24)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.post(
    "/issues/{issue_id}/transaction-questions",
    action="transaction_question.send",
    response_model=TransactionQuestionOut,
    status_code=201,
    errors=(409, 501),
)
async def ask_transaction_question_route(
    issue_id: UUID, body: TransactionQuestionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TransactionQuestionOut:
    """A person sends the firm's template wording; `communications.send` checks scope (AC-46;
    C-01-T24). Needs `closes.portal_requests` too."""
    await _human_route(ctx, "transaction_question.send")
    if not await flag_enabled(ctx.tenant, CLOSES_PORTAL_REQUESTS):
        raise NotFound(CLOSES_PORTAL_REQUESTS.name)
    _not_yet()


@close_work_router.get(f"{_C}/flux", action="flux.read", response_model=FluxSetOut, errors=(501,))
async def close_flux_route(
    close_id: UUID, ctx: Ctx, basis: Annotated[FluxBasis, Query()] = "mom"
) -> FluxSetOut:
    """CLS-10 sets and lines (AC-48; C-01-T25)."""
    await _engine_on(ctx)
    _not_yet()


@close_work_router.get(f"{_C}/flux.xlsx", action="flux.read", response_model=bytes, errors=(501,))
async def close_flux_xlsx_route(
    close_id: UUID, ctx: Ctx, basis: Annotated[FluxBasis, Query()] = "mom"
) -> Response:
    await _engine_on(ctx)
    _not_yet()


@close_work_router.post(
    "/analytic-lines/{line_id}/explain",
    action="flux.explain",
    response_model=StartedRunOut,
    status_code=202,
    errors=(409, 501),
)
async def explain_flux_line_route(
    line_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> StartedRunOut:
    """A person starts `close.agent` mode `flux` (C-01-T30)."""
    await _human_route(ctx, "flux.explain")
    _not_yet()


@close_work_router.put(
    "/analytic-lines/{line_id}/explanation",
    action="flux.edit",
    response_model=FluxLineOut,
    errors=(409, 501),
)
async def edit_flux_explanation_route(
    line_id: UUID, body: FluxExplanationIn, ctx: Ctx, if_match: IfMatch
) -> FluxLineOut:
    await _human_route(ctx, "flux.edit")
    _not_yet()


@close_work_router.post(
    "/analytic-lines/{line_id}/accept",
    action="flux.accept",
    response_model=FluxLineOut,
    errors=(409, 501),
)
async def accept_flux_line_route(line_id: UUID, ctx: Ctx, if_match: IfMatch) -> FluxLineOut:
    """A Manager or Partner accepts; a Senior 403; never the agent (AC-49; C-01-T25)."""
    await _human_route(ctx, "flux.accept")
    _not_yet()


@portal_close_router.get(
    "/closes/{close_id}/questions",
    action="transaction_question.read_own",
    response_model=PortalQuestionsOut,
    errors=(501,),
)
async def portal_close_questions_route(close_id: UUID, ctx: Ctx) -> PortalQuestionsOut:
    """POR-11's questions, inside the grant (INV-4; C-01-T27)."""
    await _portal_on(ctx)
    _not_yet()


@portal_close_router.post(
    "/questions/{question_id}/answer",
    action="transaction_question.answer",
    response_model=PortalQuestionOut,
    errors=(409, 501),
)
async def portal_answer_question_route(
    question_id: UUID, body: PortalAnswerIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> PortalQuestionOut:
    """The client's answer, sealed; an attachment fulfils the linked request (C-01-T27)."""
    await _portal_on(ctx)
    _not_yet()
