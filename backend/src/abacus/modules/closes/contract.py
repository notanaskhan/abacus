"""The closes contract, stub PR 1: portfolio, record, runs and plans (C-01-T04; C-01 §4.3, §4.4;
SPEC-655 F1, F2, F4; `docs/contracts/closes.md`). Screens CLS-01, CLS-02, CLS-09.

Every route answers, in order: a client principal 404 (the firm's close is never a portal
route); `closes.engine` off for the firm 404 (dark until the flip, AC-54); a human-only route
refuses any actor that is not a live person 403 (INV-1, AC-12); then 501 until its build task
(T14 record and status, T15 plans, T20 runs). Fixture mode serves the screens meanwhile.

Classification (ADR-031): client and account names, plan text and run meta are `confidential`;
identifiers, states and counts are `internal`. Nothing here is TRI. Money is `Decimal`.

Module API for consumers (C-01 §4.4): `close_for` (C-02, K-04, I-01, P-08) and the fail-closed
`register_status_guard` slot C-02 fills for Approved, Delivered and Locked (AC-11).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Final, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CLOSES_ENGINE
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=64)]
Internal = classified("internal")
Confidential = classified("confidential")
Period = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"), Internal]

CloseStatus = Literal["not_started", "in_progress", "in_review", "approved", "delivered", "locked"]
GuardedStatus = Literal["approved", "delivered", "locked"]
ProcedureStatus = Literal["queued", "running", "needs_attention", "done", "failed"]
ProcedureKind = Literal[
    "reconciliation",
    "aging",
    "clear_and_age",
    "third_party_sales",
    "rollforward",
    "amortization",
    "depreciation",
    "aging_cutoff",
    "accrual",
    "tie_to_return",
    "tie_to_filings",
    "recategorize",
    "flux",
]
PlanSource = Literal[
    "bank_feed", "client_upload", "quickbooks_online", "files", "accrued_register"
]
ReviewLevel = Literal["senior_signoff", "manager_approval"]
Frequency = Literal["monthly", "quarterly", "annual"]
PlanVersionStatus = Literal["draft", "published", "discarded"]
RunScope = Literal["all", "group", "failed_only", "accounts"]
RunStatus = Literal["running", "needs_input", "complete", "complete_with_exceptions", "failed"]
CloseAction = Literal[
    "close.assign",
    "close.status_move",
    "close_run.start",
    "close_run.retry",
    "close_plan.edit",
    "close_plan.request_publish",
    "close_plan.publish",
    "close_plan.draft_from_history",
]
# DV-6: targets that render as planned links, with their names, until their epic lands.
PlannedTarget = Literal[
    "CLS-07", "CLS-08", "CLS-11", "CLS-12", "CLS-13", "INB-04", "HOME-03", "SHL-21"
]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- refusal codes (C-01 §4.3; docs/architecture/error-codes.yaml) -------------------------------


class AccountsNotReconciled(DomainConflict):
    """In review below 21 of 21: `facts.account_external_id` names the first account (AC-9)."""

    code = "accounts_not_reconciled"


class CloseRunInProgress(DomainConflict):
    """A run of this close is still open, so it cannot move to In review or start another."""

    code = "run_in_progress"


class TransitionNotAvailable(DomainConflict):
    """Approved, Delivered and Locked until C-02 registers their guards (fail closed, AC-11)."""

    code = "transition_not_available"


class PlanVersionPinned(DomainConflict):
    """The close's plan version was pinned at BD1 and never changes (QC-2, AC-18)."""

    code = "plan_version_pinned"


class UnadoptedRows(DomainConflict):
    """A drafted plan row nobody adopted blocks publishing (P-35; AC-22)."""

    code = "unadopted_rows"


# --- consumer API: facts and the status guard slot (C-01 §4.4) ----------------------------------


@dataclass(frozen=True)
class CloseFacts:
    """What C-02, K-04, I-01 and P-08 read about one close."""

    close_id: UUID
    engagement_id: UUID
    client_entity_id: UUID | None
    period: str
    status: CloseStatus
    on_hold: bool
    plan_version: int | None
    accounts_reconciled: int
    accounts_total: int
    open_issues: int
    attest: bool


StatusGuard = Callable[[AuthContext, UUID], Awaitable[None]]
_GUARDED: Final = frozenset({"approved", "delivered", "locked"})
_guards: dict[str, StatusGuard] = {}


def register_status_guard(to_status: GuardedStatus, guard: StatusGuard) -> None:
    """C-02's slot for Approved, Delivered and Locked; one guard per status."""
    if to_status not in _GUARDED:
        raise ValueError(f"only {sorted(_GUARDED)} take a registered guard")
    if to_status in _guards:
        raise ValueError(f"a guard for {to_status!r} is already registered")
    _guards[to_status] = guard


def status_guard(to_status: str) -> StatusGuard:
    """The registered guard, or 409 `transition_not_available` (fail closed, AC-11)."""
    guard = _guards.get(to_status)
    if guard is None:
        raise TransitionNotAvailable(facts={"to": to_status})
    return guard


async def close_for(tenant: TenantContext, work_item_id: UUID) -> CloseFacts:
    """The close's facts (C-01-T14)."""
    raise NotImplementedYet


# --- people and links ----------------------------------------------------------------------------


class ClosePersonOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    name: Annotated[str, Confidential]
    initials: Annotated[str, Field(min_length=1, max_length=3), Confidential]


class PlannedLinkOut(BaseModel):
    """DV-6: a target that renders disabled with its name until its epic lands."""

    model_config = _cfg()

    target: Annotated[PlannedTarget, Internal]
    label: Annotated[str, Confidential]


# --- CLS-01 portfolio ----------------------------------------------------------------------------


class CloseRowOut(BaseModel):
    """One client's close for the period (CLS-01 a): every figure is code (AC-2, AC-3)."""

    model_config = _cfg()

    close_id: Annotated[UUID, Internal]
    engagement_id: Annotated[UUID, Internal]
    client_entity_id: Annotated[UUID | None, Internal]
    client_name: Annotated[str, Confidential]
    period: Period
    status: Annotated[CloseStatus, Internal]
    on_hold: Annotated[bool, Internal] = False
    attest: Annotated[bool, Internal] = False
    accounts_reconciled: Annotated[int, Field(ge=0), Internal]
    accounts_total: Annotated[int, Field(ge=0), Internal]
    reconciled_pct: Annotated[int, Field(ge=0, le=100), Internal]
    open_issues: Annotated[int, Field(ge=0), Internal]
    due_on: Annotated[date | None, Internal] = None
    days_past_due: Annotated[int | None, Field(ge=1), Internal] = None  # firm business days
    preparer: ClosePersonOut | None = None
    reviewer: ClosePersonOut | None = None
    running: Annotated[bool, Internal] = False
    run_no: Annotated[int, Field(ge=0), Internal] = 0
    allowed_actions: Annotated[list[CloseAction], Internal] = []


class CloseTilesOut(BaseModel):
    """Four tiles (DV-9, QC-6): Approved counts under In review, Locked under Delivered."""

    model_config = _cfg()

    not_started: Annotated[int, Field(ge=0), Internal]
    in_progress: Annotated[int, Field(ge=0), Internal]
    in_review: Annotated[int, Field(ge=0), Internal]
    delivered: Annotated[int, Field(ge=0), Internal]


class CloseSummaryLineOut(BaseModel):
    """ "51 open issues · 2 past due · 3 running" (CLS-01 a)."""

    model_config = _cfg()

    open_issues: Annotated[int, Field(ge=0), Internal]
    past_due: Annotated[int, Field(ge=0), Internal]
    running: Annotated[int, Field(ge=0), Internal]


class CloseListOut(BaseModel):
    """The list envelope (ADR P-36) with the tiles and the summary line; walled closes are
    absent from all three (INV-3, AC-4)."""

    model_config = _cfg()

    items: list[CloseRowOut]
    tiles: CloseTilesOut
    summary: CloseSummaryLineOut
    next_cursor: Annotated[str | None, Internal] = None


class RunningCloseOut(BaseModel):
    """The running pill and popover: "Run 2 · 6 of 9 complete · started 9:06 AM"."""

    model_config = _cfg()

    close_id: Annotated[UUID, Internal]
    client_name: Annotated[str, Confidential]
    period: Period
    run_id: Annotated[UUID, Internal]
    run_no: Annotated[int, Field(ge=1), Internal]
    done: Annotated[int, Field(ge=0), Internal]
    total: Annotated[int, Field(ge=0), Internal]
    started_at: Annotated[datetime, Internal]


class RunningClosesOut(BaseModel):
    model_config = _cfg()

    items: list[RunningCloseOut]


# --- CLS-02 the close record ---------------------------------------------------------------------


class CloseSyncOut(BaseModel):
    """The rail's sync line, in `ledger_sync` words (C9 v2.1 sync facts)."""

    model_config = _cfg()

    state: Annotated[
        Literal["synced", "syncing", "rate_limited", "needs_reauth", "paused", "not_connected"],
        Internal,
    ]
    last_synced_at: Annotated[datetime | None, Internal] = None
    next_sync_at: Annotated[datetime | None, Internal] = None


class ClosePortalBlockOut(BaseModel):
    """The rail's client portal block: Tess Moreno "Active", Requests 2 pending, Messages."""

    model_config = _cfg()

    contact_name: Annotated[str | None, Confidential] = None
    portal_status: Annotated[Literal["active", "invited", "none"], Internal] = "none"
    requests_pending: Annotated[int, Field(ge=0), Internal] = 0
    messages: PlannedLinkOut | None = None  # INB-04 (N-03), planned


class CloseSummaryOut(BaseModel):
    """CLS-02's record: header, Summary rail and details (AC-7) with `allowed_actions`."""

    model_config = _cfg()

    close_id: Annotated[UUID, Internal]
    engagement_id: Annotated[UUID, Internal]
    engagement_name: Annotated[str, Confidential]
    client_id: Annotated[UUID, Internal]
    client_entity_id: Annotated[UUID | None, Internal]
    client_name: Annotated[str, Confidential]
    period: Period
    previous_period_close_id: Annotated[UUID | None, Internal] = None
    next_period_close_id: Annotated[UUID | None, Internal] = None
    status: Annotated[CloseStatus, Internal]
    on_hold: Annotated[bool, Internal] = False
    on_hold_reason: Annotated[str | None, Confidential] = None
    attest: Annotated[bool, Internal] = False
    preparer: ClosePersonOut | None = None
    reviewer: ClosePersonOut | None = None
    open_issues: Annotated[int, Field(ge=0), Internal]
    documents_in_binder: Annotated[int, Field(ge=0), Internal]
    accounts_reconciled: Annotated[int, Field(ge=0), Internal]
    accounts_total: Annotated[int, Field(ge=0), Internal]
    due_on: Annotated[date | None, Internal] = None
    days_past_due: Annotated[int | None, Field(ge=1), Internal] = None
    requests_publish_on: Annotated[date | None, Internal] = None
    plan_version: Annotated[int | None, Field(ge=1), Internal] = None
    run_no: Annotated[int, Field(ge=0), Internal] = 0
    sync: CloseSyncOut | None = None
    portal: ClosePortalBlockOut
    in_review_blocked_by: Annotated[str | None, Internal] = None  # the reason code shown
    planned_links: list[PlannedLinkOut] = []
    allowed_actions: Annotated[list[CloseAction], Internal] = []
    row_version: Annotated[int, Field(ge=1), Internal]


class AssigneesIn(BaseModel):
    model_config = _cfg()

    preparer_user_id: Annotated[UUID | None, Internal] = None
    reviewer_user_id: Annotated[UUID | None, Internal] = None


class OnHoldIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class StatusMoveIn(BaseModel):
    """In review or back to In progress, or the On hold flag set or cleared (DF-23). Approved,
    Delivered and Locked are C-02's guarded transitions (409 `transition_not_available`)."""

    model_config = _cfg()

    to: Annotated[Literal["in_review", "in_progress"] | GuardedStatus | None, Internal] = None
    on_hold: OnHoldIn | None = None
    clear_hold: Annotated[bool, Internal] = False


class GenerateClosesIn(BaseModel):
    """Twelve closes YYYY-01…YYYY-12 for a `cas_monthly_close` engagement (AC-13)."""

    model_config = _cfg()

    year: Annotated[int, Field(ge=2000, le=2100), Internal]


class GenerateClosesOut(BaseModel):
    model_config = _cfg()

    close_ids: Annotated[list[UUID], Internal]


# --- CLS-02 runs (a C6 v2 projection with task groups) -------------------------------------------


class CloseProcedureOut(BaseModel):
    """One procedure of a run (one step attempt; a retry is a new row)."""

    model_config = _cfg()

    procedure_id: Annotated[UUID, Internal]
    run_step_id: Annotated[UUID, Internal]
    label: Annotated[str, Confidential]  # "Reconcile Front Range Bank ••4410"
    account_external_id: Annotated[str | None, Internal] = None
    status: Annotated[ProcedureStatus, Internal]
    meta: Annotated[str | None, Confidential] = None
    open_count: Annotated[int, Field(ge=0), Internal] = 0
    failure: Annotated[str | None, Confidential] = None  # "Stopped at Shopify: …"
    decision_card_id: Annotated[UUID | None, Internal] = None  # a close_treatment card (AC-29)
    retry_of: Annotated[UUID | None, Internal] = None


class CloseTaskGroupOut(BaseModel):
    """A task group by procedure type ("Reconcile to Statements 3")."""

    model_config = _cfg()

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$"), Internal]
    label: Annotated[str, Confidential]
    procedures: list[CloseProcedureOut]


class CloseRunOut(BaseModel):
    """The run card: "6 of 9 complete · 3 running at once" (AC-28 to AC-31)."""

    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    run_no: Annotated[int, Field(ge=1), Internal]
    status: Annotated[RunStatus, Internal]
    started_by: ClosePersonOut
    started_at: Annotated[datetime, Internal]
    finished_at: Annotated[datetime | None, Internal] = None
    done: Annotated[int, Field(ge=0), Internal]
    total: Annotated[int, Field(ge=0), Internal]
    running: Annotated[int, Field(ge=0, le=3), Internal]  # never more than 3 at once
    open_issues: Annotated[int, Field(ge=0), Internal]
    read_only: Annotated[bool, Internal] = False  # an earlier run in the history
    groups: list[CloseTaskGroupOut]


class CloseRunHistoryItemOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    run_no: Annotated[int, Field(ge=1), Internal]
    status: Annotated[RunStatus, Internal]
    total: Annotated[int, Field(ge=0), Internal]
    started_at: Annotated[datetime, Internal]


class CloseRunsOut(BaseModel):
    model_config = _cfg()

    items: list[CloseRunHistoryItemOut]
    ready_to_run: Annotated[int, Field(ge=0), Internal] = 0  # "Ready to run 22 tasks" (c)


class StartRunIn(BaseModel):
    model_config = _cfg()

    scope: Annotated[RunScope, Internal] = "all"
    group_key: Annotated[str | None, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$"), Internal] = None
    account_external_ids: Annotated[list[str], Field(max_length=200), Internal] = []
    confirm_open_requests: Annotated[bool, Internal] = False  # the confirm's "Start run" (AC-6)


class StartRunOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    run_no: Annotated[int, Field(ge=1), Internal]


# --- CLS-09 close plans --------------------------------------------------------------------------


class ThresholdRefOut(BaseModel):
    """A row's threshold cell; it links to KNW-04 (K-02)."""

    model_config = _cfg()

    policy_version_id: Annotated[UUID, Internal]
    label: Annotated[str, Confidential]


class PlanRowOut(BaseModel):
    model_config = _cfg()

    row_id: Annotated[UUID, Internal]
    position: Annotated[int, Field(ge=0), Internal]
    account_external_id: Annotated[str | None, Internal] = None
    account_name: Annotated[str, Confidential]
    account_class: Annotated[str, Confidential]
    procedure: Annotated[ProcedureKind, Internal]
    method: Annotated[str, Confidential]
    evidence_required: Annotated[str | None, Confidential] = None
    source: Annotated[PlanSource, Internal]
    review_level: Annotated[ReviewLevel, Internal]
    frequency: Annotated[Frequency, Internal]  # a word, never a cron string
    threshold: ThresholdRefOut | None = None
    drafted: Annotated[bool, Internal] = False  # outlined tick until adopted (CLS-09 c)
    adopted: Annotated[bool, Internal] = True
    changed_from_previous: Annotated[bool, Internal] = False  # "Changed" (CLS-09 b)


class RequestTemplateOut(BaseModel):
    model_config = _cfg()

    template_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    category_path: Annotated[list[str], Confidential]
    due_business_day: Annotated[int, Field(ge=1, le=20), Internal]
    client_visible: Annotated[bool, Internal]  # bank-feed rows are internal-only (QC-1)


class PlanTallyOut(BaseModel):
    """ "23 procedures = Manager 8 + Senior 15 · 8 requests a month" (CLS-09 a)."""

    model_config = _cfg()

    procedures: Annotated[int, Field(ge=0), Internal]
    manager: Annotated[int, Field(ge=0), Internal]
    senior: Annotated[int, Field(ge=0), Internal]
    requests_per_month: Annotated[int, Field(ge=0), Internal]


class PlanVersionOut(BaseModel):
    model_config = _cfg()

    plan_id: Annotated[UUID, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    status: Annotated[PlanVersionStatus, Internal]
    effective_from: Annotated[str | None, Internal] = None
    change_note: Annotated[str | None, Confidential] = None
    drafted_by: Annotated[str, Confidential]  # "Raj Malhotra via Agent · Close Planner" (DV-4)
    published_by: ClosePersonOut | None = None
    published_at: Annotated[datetime | None, Internal] = None
    publish_requested: Annotated[bool, Internal] = False
    rows: list[PlanRowOut]
    request_templates: list[RequestTemplateOut]
    tally: PlanTallyOut
    allowed_actions: Annotated[list[CloseAction], Internal] = []
    row_version: Annotated[int, Field(ge=1), Internal]


class PlanHistoryItemOut(BaseModel):
    model_config = _cfg()

    version: Annotated[int, Field(ge=1), Internal]
    status: Annotated[PlanVersionStatus, Internal]
    attribution: Annotated[str, Confidential]  # "v1 drafted · Raj Malhotra via Agent · …"
    at: Annotated[datetime, Internal]


class PlanHistoryOut(BaseModel):
    model_config = _cfg()

    items: list[PlanHistoryItemOut]


class PlanDraftIn(BaseModel):
    model_config = _cfg()

    from_version: Annotated[int | None, Field(ge=1), Internal] = None


class PlanRowIn(BaseModel):
    model_config = _cfg()

    account_external_id: Annotated[str | None, Field(max_length=64), Internal] = None
    account_name: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    account_class: Annotated[str, Field(min_length=1, max_length=64), Confidential]
    procedure: Annotated[ProcedureKind, Internal]
    method: Annotated[str, Field(min_length=1, max_length=500), Confidential]
    evidence_required: Annotated[str | None, Field(max_length=500), Confidential] = None
    source: Annotated[PlanSource, Internal]
    review_level: Annotated[ReviewLevel, Internal]
    frequency: Annotated[Frequency, Internal] = "monthly"
    threshold_policy_version_id: Annotated[UUID | None, Internal] = None


class PlanRowPatchIn(BaseModel):
    model_config = _cfg()

    procedure: Annotated[ProcedureKind | None, Internal] = None
    method: Annotated[str | None, Field(min_length=1, max_length=500), Confidential] = None
    evidence_required: Annotated[str | None, Field(max_length=500), Confidential] = None
    source: Annotated[PlanSource | None, Internal] = None
    review_level: Annotated[ReviewLevel | None, Internal] = None
    frequency: Annotated[Frequency | None, Internal] = None
    threshold_policy_version_id: Annotated[UUID | None, Internal] = None


class RequestTemplateIn(BaseModel):
    model_config = _cfg()

    title: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    category_path: Annotated[list[str], Field(max_length=6), Confidential] = []
    due_business_day: Annotated[int, Field(ge=1, le=20), Internal]
    client_visible: Annotated[bool, Internal] = True


class PublishIn(BaseModel):
    """ "applies from the September 2026 close; August stays on v3" (CLS-09 b2)."""

    model_config = _cfg()

    effective_from: Period


class AdoptOut(BaseModel):
    model_config = _cfg()

    adopted: Annotated[int, Field(ge=0), Internal]
    row_version: Annotated[int, Field(ge=1), Internal]


class DraftFromHistoryOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    version: Annotated[int, Field(ge=1), Internal]


class CloseTemplateOut(BaseModel):
    """An industry template card (CLS-09 d): DB content, imported (AC-20)."""

    model_config = _cfg()

    template_id: Annotated[UUID, Internal]
    key: Annotated[str, Internal]
    name: Annotated[str, Confidential]
    version: Annotated[int, Field(ge=1), Internal]
    procedures: Annotated[int, Field(ge=0), Internal]
    requests: Annotated[int, Field(ge=0), Internal]


class CloseTemplatesOut(BaseModel):
    model_config = _cfg()

    items: list[CloseTemplateOut]


class CloseTemplateImportIn(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$"), Internal]
    name: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    version: Annotated[int, Field(ge=1), Internal]
    rows: Annotated[list[PlanRowIn], Field(min_length=1, max_length=200)]
    request_templates: Annotated[list[RequestTemplateIn], Field(max_length=100)] = []


# --- routes (each 501, one action) ---------------------------------------------------------------

closes_router = AbacusRouter(prefix="/v1", tags=["closes"])
_C = "/closes/{close_id}"
_P = "/clients/{client_id}/close-plan"


async def _engine_on(ctx: AuthContext) -> None:
    """A client principal never reaches a firm close route; the flag off answers 404."""
    if ctx.client or not await flag_enabled(ctx.tenant, CLOSES_ENGINE):
        raise NotFound(CLOSES_ENGINE.name)


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform, a client or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _human_route(ctx: AuthContext, action: str) -> None:
    await _engine_on(ctx)
    _human(ctx, action)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@closes_router.get("/closes", action="close.read", response_model=CloseListOut, errors=(501,))
async def list_closes_route(
    ctx: Ctx,
    period: Annotated[str, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")],
    status: Annotated[CloseStatus | Literal["past_due"] | None, Query()] = None,
    preparer: Annotated[UUID | None, Query()] = None,
    reviewer: Annotated[UUID | None, Query()] = None,
    attest: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> CloseListOut:
    """CLS-01 rows, tiles and the summary line through `visible()` (C-01-T14)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.get(
    "/closes/running", action="close.read", response_model=RunningClosesOut, errors=(501,)
)
async def running_closes_route(ctx: Ctx) -> RunningClosesOut:
    """The running pill and popover (C-01-T20)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.get(_C, action="close.read", response_model=CloseSummaryOut, errors=(501,))
async def close_summary_route(close_id: UUID, ctx: Ctx) -> CloseSummaryOut:
    """CLS-02's record; a walled close answers 404 (AC-4; C-01-T14)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.put(
    f"{_C}/assignees", action="close.assign", response_model=CloseSummaryOut, errors=(409, 501)
)
async def close_assignees_route(
    close_id: UUID, body: AssigneesIn, ctx: Ctx, if_match: IfMatch
) -> CloseSummaryOut:
    """Managers and Partners reassign preparer and reviewer (AC-8; C-01-T14)."""
    await _human_route(ctx, "close.assign")
    _not_yet()


@closes_router.post(
    f"{_C}/status", action="close.status_move", response_model=CloseSummaryOut, errors=(409, 501)
)
async def close_status_route(
    close_id: UUID, body: StatusMoveIn, ctx: Ctx, if_match: IfMatch
) -> CloseSummaryOut:
    """Gated moves and the On hold flag (AC-9 to AC-12; C-01-T14): 409
    `accounts_not_reconciled`, `run_in_progress` or `transition_not_available`."""
    await _human_route(ctx, "close.status_move")
    _not_yet()


@closes_router.post(
    "/engagements/{engagement_id}/closes:generate",
    action="close.create",
    response_model=GenerateClosesOut,
    status_code=201,
    errors=(409, 501),
)
async def generate_closes_route(
    engagement_id: UUID, body: GenerateClosesIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> GenerateClosesOut:
    """Twelve closes for a Monthly close engagement; a period that exists answers 409
    `work_item_exists` (AC-13; C-01-T14)."""
    await _human_route(ctx, "close.create")
    _not_yet()


@closes_router.post(
    f"{_C}/runs",
    action="close_run.start",
    response_model=StartRunOut,
    status_code=202,
    errors=(409, 501),
)
async def start_close_run_route(
    close_id: UUID, body: StartRunIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> StartRunOut:
    """A live person starts a run; code plans it (AC-28; C-01-T20)."""
    await _human_route(ctx, "close_run.start")
    _not_yet()


@closes_router.get(f"{_C}/runs", action="close.read", response_model=CloseRunsOut, errors=(501,))
async def close_runs_route(close_id: UUID, ctx: Ctx) -> CloseRunsOut:
    """Run history ("Run 2 ⌄"; AC-31; C-01-T20)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.get(
    f"{_C}/runs/{{run_no}}", action="close.read", response_model=CloseRunOut, errors=(501,)
)
async def close_run_route(
    close_id: UUID, run_no: Annotated[int, Path(ge=1)], ctx: Ctx
) -> CloseRunOut:
    """The run view over C6 v2 with task groups (C-01-T20)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.post(
    f"{_C}/runs/{{run_no}}/steps/{{step_id}}/retry",
    action="close_run.retry",
    response_model=CloseProcedureOut,
    status_code=202,
    errors=(409, 501),
)
async def retry_close_procedure_route(
    close_id: UUID,
    run_no: Annotated[int, Path(ge=1)],
    step_id: UUID,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> CloseProcedureOut:
    """Retry a failed procedure as a new step row (AC-30; C-01-T20)."""
    await _human_route(ctx, "close_run.retry")
    _not_yet()


@closes_router.get(_P, action="close_plan.read", response_model=PlanVersionOut, errors=(501,))
async def close_plan_route(
    client_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> PlanVersionOut:
    """The published plan (or a version) with rows, requests and tally (AC-14; C-01-T15)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.get(
    f"{_P}/versions", action="close_plan.read", response_model=PlanHistoryOut, errors=(501,)
)
async def close_plan_history_route(client_id: UUID, ctx: Ctx) -> PlanHistoryOut:
    """History with "<person> via Agent" attribution (AC-15; C-01-T15)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.post(
    f"{_P}/drafts",
    action="close_plan.edit",
    response_model=PlanVersionOut,
    status_code=201,
    errors=(409, 501),
)
async def create_plan_draft_route(client_id: UUID, body: PlanDraftIn, ctx: Ctx) -> PlanVersionOut:
    """Draft v(n+1) from a version; one draft per plan (AC-16; C-01-T15)."""
    await _human_route(ctx, "close_plan.edit")
    _not_yet()


@closes_router.patch(
    f"{_P}/drafts/{{version}}/rows/{{row_id}}",
    action="close_plan.edit",
    response_model=PlanRowOut,
    errors=(409, 501),
)
async def patch_plan_row_route(
    client_id: UUID,
    version: Annotated[int, Path(ge=1)],
    row_id: UUID,
    body: PlanRowPatchIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> PlanRowOut:
    """409 `stale_version` (the repo's code for a stale If-Match) names the other editor (AC-19;
    C-01-T15)."""
    await _human_route(ctx, "close_plan.edit")
    _not_yet()


@closes_router.post(
    f"{_P}/drafts/{{version}}/rows",
    action="close_plan.edit",
    response_model=PlanRowOut,
    status_code=201,
    errors=(409, 501),
)
async def add_plan_row_route(
    client_id: UUID,
    version: Annotated[int, Path(ge=1)],
    body: PlanRowIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> PlanRowOut:
    await _human_route(ctx, "close_plan.edit")
    _not_yet()


@closes_router.post(
    f"{_P}/drafts/{{version}}/request-templates",
    action="close_plan.edit",
    response_model=RequestTemplateOut,
    status_code=201,
    errors=(409, 501),
)
async def add_request_template_route(
    client_id: UUID,
    version: Annotated[int, Path(ge=1)],
    body: RequestTemplateIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> RequestTemplateOut:
    await _human_route(ctx, "close_plan.edit")
    _not_yet()


@closes_router.post(
    f"{_P}/drafts/{{version}}/publish",
    action="close_plan.publish",
    response_model=PlanVersionOut,
    errors=(409, 501),
)
async def publish_plan_route(
    client_id: UUID,
    version: Annotated[int, Path(ge=1)],
    body: PublishIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> PlanVersionOut:
    """A Manager or Partner publishes; 409 `unadopted_rows` (AC-17, AC-22; C-01-T15)."""
    await _human_route(ctx, "close_plan.publish")
    _not_yet()


@closes_router.post(
    f"{_P}/drafts/{{version}}/request-publish",
    action="close_plan.request_publish",
    response_model=PlanVersionOut,
    errors=(409, 501),
)
async def request_plan_publish_route(
    client_id: UUID, version: Annotated[int, Path(ge=1)], ctx: Ctx
) -> PlanVersionOut:
    """One `close_plan_publish_requested` gate for Managers and Partners (QC-8; C-01-T15)."""
    await _human_route(ctx, "close_plan.request_publish")
    _not_yet()


@closes_router.post(
    f"{_P}/draft-from-history",
    action="close_plan.draft_from_history",
    response_model=DraftFromHistoryOut,
    status_code=202,
    errors=(409, 501),
)
async def draft_plan_from_history_route(
    client_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DraftFromHistoryOut:
    """A person starts `close.agent` mode `planner` (AC-21; C-01-T30)."""
    await _human_route(ctx, "close_plan.draft_from_history")
    _not_yet()


@closes_router.post(
    f"{_P}/drafts/{{version}}/rows/{{row_id}}:adopt",
    action="suggestion.resolve",
    response_model=AdoptOut,
    errors=(409, 501),
)
async def adopt_plan_row_route(
    client_id: UUID,
    version: Annotated[int, Path(ge=1)],
    row_id: UUID,
    ctx: Ctx,
    if_match: IfMatch,
) -> AdoptOut:
    """A person adopts a drafted row (P-35 suggestion resolve; AC-22; C-01-T15)."""
    await _human_route(ctx, "suggestion.resolve")
    _not_yet()


@closes_router.post(
    f"{_P}/drafts/{{version}}/rows:adopt-all",
    action="suggestion.resolve",
    response_model=AdoptOut,
    errors=(409, 501),
)
async def adopt_all_plan_rows_route(
    client_id: UUID, version: Annotated[int, Path(ge=1)], ctx: Ctx, if_match: IfMatch
) -> AdoptOut:
    """ "Adopt all" by a Senior or above (C-01-T15)."""
    await _human_route(ctx, "suggestion.resolve")
    _not_yet()


@closes_router.get(
    "/close-templates", action="close_plan.read", response_model=CloseTemplatesOut, errors=(501,)
)
async def close_templates_route(ctx: Ctx) -> CloseTemplatesOut:
    """The firm's industry templates (CLS-09 d; C-01-T15)."""
    await _engine_on(ctx)
    _not_yet()


@closes_router.post(
    "/close-templates:import",
    action="close_template.import",
    response_model=CloseTemplateOut,
    status_code=201,
    errors=(409, 501),
)
async def import_close_template_route(
    body: CloseTemplateImportIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> CloseTemplateOut:
    """DB content through an import, never a commit (AC-20; C-01-T15)."""
    await _human_route(ctx, "close_template.import")
    _not_yet()
