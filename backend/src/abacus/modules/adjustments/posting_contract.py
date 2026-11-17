"""C8 v2 posting stub (C-02-T06; SPEC-700 AC-3; ADR-344; `docs/contracts/adjustments.md` v2).
Screen family CLS-07 (Proposed entries: approvals and posting).

Every route answers, in order: a client principal 404 (no portal route posts); the
`adjustments.posting` flag off for the firm 404; a human-only route refuses an agent, the
platform, a client or a support session 403 (INV-1, AC-10); then 501 `not_implemented` until its
build task (C-02-T12 approvals, T13 the W1 writer, T18 the dry run and posting, T19 retries and
conflicts, T22 record external). Fixture mode serves CLS-07 meanwhile.

Classification (ADR-031): account names, descriptions and provider messages are `confidential`;
identifiers, states, counts and amounts' codes are `internal`. Money is `Decimal`, summed by code
(ADR-050). Seed examples are Copperleaf's August 2026 batch (SPEC-700 §3).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from abacus.kernel._flags import ADJUSTMENTS_POSTING
from abacus.kernel._statuses import (
    ClosingDateConflictStatus,
    PostingBatchStatus,
    ProposedEntryStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Money = Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=2), Confidential]

EntryStatus = ProposedEntryStatus  # the `proposed_entry` registry object (C-02-T03)
BatchStatus = PostingBatchStatus  # the `posting_batch` registry object (C-02-T03)
ConflictStatus = ClosingDateConflictStatus
PreflightCheck = Literal[
    "balanced", "open_period", "mapped_accounts", "active_accounts", "closing_date_unlocked"
]
RefusalCode = Literal[
    "inactive_account",
    "unmapped_account",
    "closing_date_locked",
    "attest_client_posting_refused",
    "write_grant_missing",
    "write_capability_disabled",
    "write_capability_not_released",
    "posting_not_enabled",
]
EntryAction = Literal[
    "proposed_entry.approve",
    "proposed_entry.request_approval",
    "proposed_entry.undo_approval",
    "proposed_entry.withdraw_approval",
    "proposed_entry.reject_close",
    "proposed_entry.record_external",
    "posting_batch.post",
]


def _cfg(example: dict[str, object] | None = None) -> ConfigDict:
    if example is None:
        return ConfigDict(frozen=True, extra="forbid")
    extra = cast(JsonDict, {"examples": [example]})
    return ConfigDict(frozen=True, extra="forbid", json_schema_extra=extra)


# --- CLS-07 list and detail ------------------------------------------------------------------


class PostingTallyOut(BaseModel):
    """One tile of the CLS-07 tally strip: a count and code's sum."""

    model_config = _cfg({"count": 4, "amount": "20020.00"})

    count: Annotated[int, Field(ge=0), Internal]
    amount: Money


class PostingTalliesOut(BaseModel):
    """CLS-07a: PROPOSED 5 · $34,920.00, WITHIN 4 · $20,020.00, REVIEW 1 · $14,900.00, APPROVED
    0 of 5, POSTED Pending."""

    model_config = _cfg()

    proposed: Annotated[PostingTallyOut, Internal]
    within_threshold: Annotated[PostingTallyOut, Internal]
    review_required: Annotated[PostingTallyOut, Internal]
    approved: Annotated[int, Field(ge=0), Internal]
    of: Annotated[int, Field(ge=0), Internal]
    posted_batch_code: Annotated[str | None, Internal] = None


class PostingClassLimitOut(BaseModel):
    model_config = _cfg({"account_class": "payroll_accruals", "limit": "15000.00"})

    account_class: Annotated[str, Field(max_length=60), Internal]
    limit: Money


class PostingCloseEntryRowOut(BaseModel):
    """A CLS-07 row: AJE-05 · Review required · > $10,000 other accruals."""

    model_config = _cfg(
        {
            "entry_id": "00000000-0000-4000-8000-000000000005",
            "ref": "AJE-05",
            "description": "Accrued utilities — August",
            "amount": "14900.00",
            "status": ProposedEntryStatus.REVIEW_REQUIRED.value,
            "class_limit": {"account_class": "other_accruals", "limit": "10000.00"},
            "approval_label": None,
            "external_txn_ref": None,
            "reverses_on": "2026-09-01",
            "version": 1,
            "allowed_actions": ["proposed_entry.request_approval"],
        }
    )

    entry_id: Annotated[UUID, Internal]
    ref: Annotated[str, Field(pattern=r"^(AJE|RJE|PAJE)-[1-9][0-9]{0,3}$"), Internal]
    description: Annotated[str | None, Field(max_length=500), Confidential] = None
    amount: Money
    status: Annotated[EntryStatus, Internal]
    class_limit: Annotated[PostingClassLimitOut | None, Internal] = None
    approval_label: Annotated[str | None, Field(max_length=200), Confidential] = None
    external_txn_ref: Annotated[str | None, Field(max_length=64), Internal] = None
    reverses_on: Annotated[date | None, Internal] = None
    version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[EntryAction], Internal] = []


class PostingApproverContextOut(BaseModel):
    """The footer: "Approving as Raj Malhotra · CAS Senior · may approve within-threshold
    batches under BH AJE thresholds v2"."""

    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    display_name: Annotated[str, Field(max_length=200), Confidential]
    role_label: Annotated[str, Field(max_length=60), Internal]
    policy_label: Annotated[str, Field(max_length=200), Confidential]
    policy_version_id: Annotated[UUID, Internal]
    may_batch_within_threshold: Annotated[bool, Internal]


class PostingCloseEntriesOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[PostingCloseEntryRowOut], Internal]
    total: Annotated[int, Field(ge=0), Internal]
    tallies: Annotated[PostingTalliesOut, Internal]
    approver: Annotated[PostingApproverContextOut, Internal]
    posting_enabled: Annotated[bool, Internal]
    is_attest_client: Annotated[bool, Internal]


# --- decisions ---------------------------------------------------------------------------------


class PostingApproveIn(BaseModel):
    model_config = _cfg({"seen_version": 1})

    seen_version: Annotated[int, Field(ge=1), Internal]


class PostingDecisionOut(BaseModel):
    """A written decision with its 10-second Undo window (DEC-24)."""

    model_config = _cfg()

    decision_id: Annotated[UUID, Internal]
    entry_id: Annotated[UUID, Internal]
    status: Annotated[EntryStatus, Internal]
    approval_label: Annotated[str | None, Field(max_length=200), Confidential] = None
    undo_until: Annotated[datetime | None, Internal] = None


class PostingRequestApprovalIn(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]


class PostingReasonIn(BaseModel):
    model_config = _cfg({"reason_code": "duplicate", "note": "Booked by the client on Aug 30."})

    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z_]{1,59}$"), Internal]
    note: Annotated[str | None, Field(max_length=2000), Confidential] = None


class PostingRecordExternalIn(BaseModel):
    """Recorded in ledger (export path) or Recorded by <client> (attest): evidence or a sync
    match, at least one."""

    model_config = _cfg()

    evidence_version_id: Annotated[UUID | None, Internal] = None
    match_ref: Annotated[str | None, Field(max_length=200), Internal] = None


# --- posting batches ---------------------------------------------------------------------------


class PostingEntryIdsIn(BaseModel):
    model_config = _cfg()

    entry_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), Internal]


class PostingPreflightResultOut(BaseModel):
    model_config = _cfg()

    entry_id: Annotated[UUID, Internal]
    ok: Annotated[bool, Internal]
    failed_check: Annotated[PreflightCheck | None, Internal] = None
    refusal: Annotated[RefusalCode | None, Internal] = None
    account_ref: Annotated[str | None, Field(max_length=64), Internal] = None


class PostingDryRunOut(BaseModel):
    """CLS-07c2: "Post 6 entries ($35,300.00) to QuickBooks Online · Copperleaf Coffee
    Roasters? The closing date will be set to Aug 31, 2026." No write happens."""

    model_config = _cfg(
        {
            "entry_count": 6,
            "total_amount": "35300.00",
            "ledger_label": "QuickBooks Online",
            "client_entity_name": "Copperleaf Coffee Roasters",
            "closing_date_target": "2026-08-31",
            "results": [],
        }
    )

    entry_count: Annotated[int, Field(ge=0), Internal]
    total_amount: Money
    ledger_label: Annotated[str, Field(max_length=60), Internal]
    client_entity_name: Annotated[str, Field(max_length=200), Confidential]
    closing_date_target: Annotated[date | None, Internal] = None
    results: Annotated[list[PostingPreflightResultOut], Internal]


class PostingPostBatchIn(BaseModel):
    model_config = _cfg()

    entry_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), Internal]
    seen_versions: Annotated[dict[UUID, int], Internal]
    set_closing_date: Annotated[bool, Internal] = True


class PostingBatchEntryOut(BaseModel):
    """A batch drawer row: AJE-01 · Posted · QBO 48213."""

    model_config = _cfg()

    entry_id: Annotated[UUID, Internal]
    ref: Annotated[str, Internal]
    status: Annotated[EntryStatus, Internal]
    external_txn_ref: Annotated[str | None, Field(max_length=64), Internal] = None
    deep_link: Annotated[str | None, Field(max_length=500), Internal] = None
    failure: Annotated[RefusalCode | None, Internal] = None
    provider_message: Annotated[str | None, Field(max_length=500), Confidential] = None


class PostingBatchOut(BaseModel):
    """Batch 2026-08-A: six entries, $35,300.00, QBO 48213-48218, closing date Aug 31, 2026."""

    model_config = _cfg(
        {
            "batch_id": "00000000-0000-4000-8000-0000000008a0",
            "batch_code": "2026-08-A",
            "period": "2026-08",
            "status": PostingBatchStatus.POSTED.value,
            "entry_count": 6,
            "total_amount": "35300.00",
            "first_external_ref": "48213",
            "last_external_ref": "48218",
            "closing_date_target": "2026-08-31",
            "failure_count": 0,
            "resolved_failure_count": 0,
            "undo_until": None,
            "entries": [],
            "version": 3,
        }
    )

    batch_id: Annotated[UUID, Internal]
    batch_code: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[A-Z]$"), Internal]
    period: Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"), Internal]
    status: Annotated[BatchStatus, Internal]
    entry_count: Annotated[int, Field(ge=1), Internal]
    total_amount: Money
    first_external_ref: Annotated[str | None, Internal] = None
    last_external_ref: Annotated[str | None, Internal] = None
    closing_date_target: Annotated[date | None, Internal] = None
    failure_count: Annotated[int, Field(ge=0), Internal] = 0
    resolved_failure_count: Annotated[int, Field(ge=0), Internal] = 0
    undo_until: Annotated[datetime | None, Internal] = None
    entries: Annotated[list[PostingBatchEntryOut], Internal] = []
    version: Annotated[int, Field(ge=1), Internal]


class PostingRedateIn(BaseModel):
    model_config = _cfg({"new_date": "2026-09-01", "reason": "Closing date stays Aug 31."})

    new_date: Annotated[date, Internal]
    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class PostingConflictOut(BaseModel):
    """CLS-11e: "AJE dated Aug 31 cannot post — the QuickBooks closing date is Aug 31, 2026"."""

    model_config = _cfg()

    conflict_id: Annotated[UUID, Internal]
    entry_id: Annotated[UUID, Internal]
    ledger_closing_date: Annotated[date, Internal]
    entry_date: Annotated[date, Internal]
    status: Annotated[ConflictStatus, Internal]
    client_asked_at: Annotated[datetime | None, Internal] = None


# --- routes (each 501, one action) -------------------------------------------------------------

posting_router = AbacusRouter(prefix="/v1", tags=["adjustments"])
_WI = "/work-items/{work_item_id}"


async def _posting_on(ctx: AuthContext) -> None:
    """A client principal never reaches a posting route; the flag off answers 404."""
    if ctx.client or not await flag_enabled(ctx.tenant, ADJUSTMENTS_POSTING):
        raise NotFound(ADJUSTMENTS_POSTING.name)


async def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform, a client or a support session."""
    await _posting_on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@posting_router.get(
    f"{_WI}/proposed-entries:close",
    action="proposed_entry.read",
    response_model=PostingCloseEntriesOut,
    errors=(501,),
)
async def close_entries_route(work_item_id: UUID, ctx: Ctx) -> PostingCloseEntriesOut:
    """CLS-07 list with tallies, class limits and the approver's context (C-02-T12)."""
    await _posting_on(ctx)
    raise NotImplementedYet


@posting_router.post(
    "/proposed-entries/{entry_id}/approve",
    action="proposed_entry.approve",
    response_model=PostingDecisionOut,
    errors=(409, 501),
)
async def approve_entry_route(
    entry_id: UUID, body: PostingApproveIn, ctx: Ctx
) -> PostingDecisionOut:
    """A held or review-required entry; 409 `over_approval_limit` or `snapshot_changed`; the
    10-second Undo (C-02-T12)."""
    await _human(ctx, "proposed_entry.approve")
    raise NotImplementedYet


@posting_router.post(
    "/proposed-entries/{entry_id}/request-approval",
    action="proposed_entry.request_approval",
    response_model=PostingDecisionOut,
    errors=(409, 501),
)
async def request_approval_route(
    entry_id: UUID, body: PostingRequestApprovalIn, ctx: Ctx
) -> PostingDecisionOut:
    """HOME-02 gate `proposed_entry_approval` and the bell `entry_approval_requested`."""
    await _human(ctx, "proposed_entry.request_approval")
    raise NotImplementedYet


@posting_router.post(
    "/proposed-entry-decisions/{decision_id}/undo",
    action="proposed_entry.undo_approval",
    response_model=PostingDecisionOut,
    errors=(409, 501),
)
async def undo_approval_route(decision_id: UUID, ctx: Ctx) -> PostingDecisionOut:
    """`approval_undone`, inside 10 seconds and before any effect started."""
    await _human(ctx, "proposed_entry.undo_approval")
    raise NotImplementedYet


@posting_router.post(
    "/proposed-entries/{entry_id}/withdraw-approval",
    action="proposed_entry.withdraw_approval",
    response_model=PostingDecisionOut,
    errors=(409, 501),
)
async def withdraw_approval_route(
    entry_id: UUID, body: PostingReasonIn, ctx: Ctx
) -> PostingDecisionOut:
    """`approval_withdrawn` on an approved, unposted entry; it returns to its threshold result."""
    await _human(ctx, "proposed_entry.withdraw_approval")
    raise NotImplementedYet


@posting_router.post(
    "/proposed-entries/{entry_id}/reject-close",
    action="proposed_entry.reject_close",
    response_model=PostingDecisionOut,
    errors=(409, 501),
)
async def reject_close_entry_route(
    entry_id: UUID, body: PostingReasonIn, ctx: Ctx
) -> PostingDecisionOut:
    """Rejected with a reason, and a CLS-06 issue on the close (DF-23)."""
    await _human(ctx, "proposed_entry.reject_close")
    raise NotImplementedYet


@posting_router.post(
    "/proposed-entries/{entry_id}/record-external",
    action="proposed_entry.record_external",
    response_model=PostingDecisionOut,
    errors=(409, 501),
)
async def record_external_route(
    entry_id: UUID, body: PostingRecordExternalIn, ctx: Ctx
) -> PostingDecisionOut:
    """Recorded in ledger / Recorded by <client> (C-02-T22)."""
    await _human(ctx, "proposed_entry.record_external")
    raise NotImplementedYet


@posting_router.get(
    f"{_WI}/proposed-entries.xlsx",
    action="proposed_entry.export",
    response_model=bytes,
    errors=(501,),
)
async def entries_export_route(work_item_id: UUID, ctx: Ctx) -> bytes:
    """Open in Excel and, without W1, the deterministic JE import file (export instead)."""
    await _human(ctx, "proposed_entry.export")
    raise NotImplementedYet


@posting_router.post(
    f"{_WI}/posting-batches:dry-run",
    action="posting_batch.dry_run",
    response_model=PostingDryRunOut,
    errors=(409, 501),
)
async def dry_run_route(work_item_id: UUID, body: PostingEntryIdsIn, ctx: Ctx) -> PostingDryRunOut:
    """Preflight only; no write (C-02-T18)."""
    await _human(ctx, "posting_batch.dry_run")
    raise NotImplementedYet


@posting_router.post(
    f"{_WI}/posting-batches",
    action="posting_batch.post",
    response_model=PostingBatchOut,
    status_code=202,
    errors=(409, 501),
)
async def post_batch_route(
    work_item_id: UUID, body: PostingPostBatchIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> PostingBatchOut:
    """The batch, its approval grant (`not_before = +10 s`) and `PostingBatchWorkflow`; fresh
    MFA; refused for an attest client (C-02-T18)."""
    await _human(ctx, "posting_batch.post")
    raise NotImplementedYet


@posting_router.post(
    "/posting-batches/{batch_id}/undo",
    action="posting_batch.post",
    response_model=PostingBatchOut,
    errors=(409, 501),
)
async def undo_batch_route(batch_id: UUID, ctx: Ctx) -> PostingBatchOut:
    """Void the grant inside the hold: nothing is written."""
    await _human(ctx, "posting_batch.post")
    raise NotImplementedYet


@posting_router.post(
    "/posting-batches/{batch_id}/entries/{entry_id}/retry",
    action="posting_batch.post",
    response_model=PostingBatchOut,
    status_code=202,
    errors=(409, 501),
)
async def retry_entry_route(
    batch_id: UUID, entry_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> PostingBatchOut:
    """Re-read by DocNumber and marker, then re-write under the same key (C-02-T19)."""
    await _human(ctx, "posting_batch.post")
    raise NotImplementedYet


@posting_router.post(
    "/closing-date-conflicts/{conflict_id}/ask-client",
    action="closing_date_conflict.resolve",
    response_model=PostingConflictOut,
    errors=(409, 501),
)
async def ask_client_route(conflict_id: UUID, ctx: Ctx) -> PostingConflictOut:
    """The firm's "Lift closing date request" template row, sent by a person (C-02-T19)."""
    await _human(ctx, "closing_date_conflict.resolve")
    raise NotImplementedYet


@posting_router.post(
    "/closing-date-conflicts/{conflict_id}/redate",
    action="closing_date_conflict.resolve",
    response_model=PostingConflictOut,
    errors=(409, 501),
)
async def redate_route(conflict_id: UUID, body: PostingRedateIn, ctx: Ctx) -> PostingConflictOut:
    """Withdraws the approval and re-dates; the entry is re-approved before it posts."""
    await _human(ctx, "closing_date_conflict.resolve")
    raise NotImplementedYet
