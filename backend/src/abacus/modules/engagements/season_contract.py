"""Season setup v1 stub (SS-1; T-08-T04; SPEC-710 AC-1 to AC-8; `docs/contracts/season-setup.md`).
Screen ENG-07: the roll-forward manifest in cohorts, a manager's cohort approval and the
execution that creates engagements, returns, binders, letters, consents and invitations.

Every route answers, in order: a client principal 404 (no portal route; INV-4); the
`engagements.season_setup` flag off 404; a human-only route refuses an agent, the platform or a
support session 403 (INV-1); then 501 until its build task (T-08-T09, T12).

Classification (ADR-031): client and contact names and emails are `confidential`; ids, counts,
codes and states are `internal`. A season row never carries TRI (the planner declares no `tri`).
Tallies and counts are computed by code from the manifest and the step log (ADR-050).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import ENGAGEMENTS_SEASON_SETUP
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=40)]
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]

Segment = Literal["individuals_trusts", "entities_exempt"]
CohortStatus = Literal["draft", "approved", "executing", "executed", "failed"]
# Derived on read (status vocabulary season_cohort / season_manifest_row; never stored).
CohortDisplay = Literal[
    "draft", "review_required", "approved", "queued", "executing", "executed", "failed"
]
RowDisplay = Literal["ready", "check", "excluded", "created", "failed"]
Step = Literal[
    "engagement", "returns", "assignments", "binder", "letter", "consents", "invitations"
]
ExceptionCode = Literal[
    "assignee_seasonal_not_started",
    "contact_bounced",
    "offshore_without_consent",
    "assignee_walled_or_departed",
    "signer_missing",
    "confirmation_missing",
    "binder_ambiguous",
    "continuance_changed",
]
ExclusionReason = Literal["client_departed", "not_continuing", "duplicate", "other"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class SeasonPersonOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    initials: Annotated[str, Field(max_length=4), Confidential]
    name: Annotated[str, Field(max_length=120), Confidential]


class SeasonOut(BaseModel):
    model_config = _cfg()

    season_id: Annotated[UUID, Internal]
    tax_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    manifest_id: Annotated[UUID | None, Internal] = None
    opened_at: Annotated[datetime, Internal]


class SeasonListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SeasonOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class SeasonTallyOut(BaseModel):
    """ENG-07 tally strip (AC-1): 214 · 224 · 241; created 126 = 65 + 30 + 31; 4 of 6; 3."""

    model_config = _cfg()

    engagements: Count
    returns: Count
    binders: Count
    created: Count
    cohorts_approved: Count
    cohorts: Count
    exceptions: Count


class SeasonOfficeFootingOut(BaseModel):
    model_config = _cfg()

    office_id: Annotated[UUID, Internal]
    office_name: Annotated[str, Field(max_length=80), Internal]
    returns: Count


class SeasonCohortOut(BaseModel):
    model_config = _cfg()

    cohort_id: Annotated[UUID, Internal]
    position: Annotated[int, Field(ge=1, le=99), Internal]
    office_id: Annotated[UUID, Internal]
    office_name: Annotated[str, Field(max_length=80), Internal]
    segment: Annotated[Segment, Internal]
    status: Annotated[CohortStatus, Internal]
    display: Annotated[CohortDisplay, Internal]
    engagements: Count
    returns: Count
    binders: Count
    letters: Count
    invitations: Count
    exceptions: Count
    approver: SeasonPersonOut | None = None
    approved_at: Annotated[datetime | None, Internal] = None
    queued_after: Annotated[int | None, Field(ge=1, le=99), Internal] = None
    created_rows: Count = 0
    rows_hash: Hash
    allowed_actions: Annotated[list[str], Internal] = []


class SeasonAskOptionOut(BaseModel):
    model_config = _cfg()

    code: Annotated[str, Field(max_length=40), Internal]
    label: Annotated[str, Field(max_length=120), Internal]


class SeasonAskOut(BaseModel):
    """ENG-07 e: code finds the ambiguity; the planner may phrase it; a person answers (AC-4)."""

    model_config = _cfg()

    ask_id: Annotated[UUID, Internal]
    question_code: Annotated[str, Field(max_length=60), Internal]
    row_ids: Annotated[list[UUID], Internal]
    options: Annotated[list[SeasonAskOptionOut], Internal]
    recommended_option: Annotated[str | None, Field(max_length=40), Internal] = None
    source: Annotated[Literal["code", "agent"], Internal]
    suggestion_id: Annotated[UUID | None, Internal] = None
    answered_option: Annotated[str | None, Field(max_length=40), Internal] = None
    answered_by: SeasonPersonOut | None = None


class SeasonManifestOut(BaseModel):
    model_config = _cfg()

    manifest_id: Annotated[UUID, Internal]
    season_id: Annotated[UUID, Internal]
    tax_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    version: Annotated[int, Field(ge=1), Internal]
    status: Annotated[Literal["building", "ready", "superseded"], Internal]
    built_by: SeasonPersonOut | None = None
    built_at: Annotated[datetime | None, Internal] = None
    inputs_hash: Hash
    tally: SeasonTallyOut
    offices: Annotated[list[SeasonOfficeFootingOut], Internal]
    cohorts: Annotated[list[SeasonCohortOut], Internal]
    asks: Annotated[list[SeasonAskOut], Internal] = []
    planner_available: Annotated[bool, Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class SeasonStepOut(BaseModel):
    model_config = _cfg()

    step: Annotated[Step, Internal]
    status: Annotated[Literal["ok", "failed", "pending"], Internal]
    error_code: Annotated[str | None, Field(max_length=60), Internal] = None


class SeasonManifestRowOut(BaseModel):
    """ENG-07 a, c, d rows (AC-2, AC-3): forms, carried assignments, binder, letter, consents."""

    model_config = _cfg()

    row_id: Annotated[UUID, Internal]
    cohort_id: Annotated[UUID, Internal]
    client_id: Annotated[UUID, Internal]
    client_name: Annotated[str, Field(max_length=200), Confidential]
    forms: Annotated[list[str], Internal]
    preparer: SeasonPersonOut | None = None
    reviewer: SeasonPersonOut | None = None
    signer: SeasonPersonOut | None = None
    binder_summary: Annotated[str, Field(max_length=200), Internal]
    request_count: Count
    letter_kind: Annotated[Literal["renewal", "new", "none"], Internal]
    fee_change_pct: Annotated[Decimal | None, Field(max_digits=5, decimal_places=2), Internal] = (
        None
    )
    consent_purposes: Annotated[list[str], Internal]
    signers: Count
    invitees: Annotated[list[str], Confidential]
    exception_codes: Annotated[list[ExceptionCode], Internal] = []
    sub_line: Annotated[str | None, Field(max_length=200), Confidential] = None
    display: Annotated[RowDisplay, Internal]
    steps: Annotated[list[SeasonStepOut], Internal] = []
    row_version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class SeasonManifestRowListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SeasonManifestRowOut], Internal]
    total: Count
    next_cursor: Annotated[str | None, Internal] = None


class SeasonManifestBuildIn(BaseModel):
    model_config = _cfg()

    rebuild: Annotated[bool, Internal] = False


class SeasonRowPatchIn(BaseModel):
    """Reassign a preparer, reviewer or signer to an eligible person (AC-3)."""

    model_config = _cfg()

    preparer_user_id: Annotated[UUID | None, Internal] = None
    reviewer_user_id: Annotated[UUID | None, Internal] = None
    signer_user_id: Annotated[UUID | None, Internal] = None


class SeasonRowsExcludeIn(BaseModel):
    model_config = _cfg()

    row_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), Internal]
    reason: Annotated[ExclusionReason, Internal]
    note: Annotated[str | None, Field(max_length=500), Confidential] = None


class SeasonAskAnswerIn(BaseModel):
    model_config = _cfg()

    option: Annotated[str, Field(min_length=1, max_length=40), Internal]


class SeasonCohortApproveIn(BaseModel):
    """The approval pins what the manager saw (AC-5)."""

    model_config = _cfg()

    rows_hash: Hash
    manifest_version: Annotated[int, Field(ge=1), Internal]


class SeasonCohortWithdrawIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class SeasonApprovalOut(BaseModel):
    model_config = _cfg()

    approval_id: Annotated[UUID, Internal]
    cohort_id: Annotated[UUID, Internal]
    approval_grant_id: Annotated[UUID, Internal]
    approved_by: SeasonPersonOut
    approved_at: Annotated[datetime, Internal]
    queued_after: Annotated[int | None, Field(ge=1, le=99), Internal] = None
    run_on: Annotated[date | None, Internal] = None


# --- routes (each 501, one action) -------------------------------------------------------------

season_router = AbacusRouter(prefix="/v1", tags=["engagements"])
_S = "/seasons/{tax_year}"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, ENGAGEMENTS_SEASON_SETUP):
        raise NotFound(ENGAGEMENTS_SEASON_SETUP.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@season_router.get("/seasons", action="season.read", response_model=SeasonListOut, errors=(501,))
async def seasons_route(ctx: Ctx) -> SeasonListOut:
    await _on(ctx)
    raise NotImplementedYet


@season_router.get(
    f"{_S}/manifests/{{manifest_id}}",
    action="season.read",
    response_model=SeasonManifestOut,
    errors=(501,),
)
async def season_manifest_route(tax_year: int, manifest_id: UUID, ctx: Ctx) -> SeasonManifestOut:
    await _on(ctx)
    raise NotImplementedYet


@season_router.post(
    f"{_S}/manifests",
    action="season_setup.prepare",
    response_model=SeasonManifestOut,
    status_code=202,
    errors=(409, 501),
)
async def season_manifest_build_route(
    tax_year: int, body: SeasonManifestBuildIn, ctx: Ctx, key: IdempotencyKey
) -> SeasonManifestOut:
    """Code builds the manifest, then the planner step when allowed. 409 `cohort_approved` when
    a rebuild would replace an approved cohort."""
    await _human(ctx, "season_setup.prepare")
    raise NotImplementedYet


@season_router.get(
    "/season-cohorts/{cohort_id}/rows",
    action="season.read",
    response_model=SeasonManifestRowListOut,
    errors=(501,),
)
async def season_cohort_rows_route(
    cohort_id: UUID,
    ctx: Ctx,
    exceptions_only: bool = False,
    office_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
) -> SeasonManifestRowListOut:
    await _on(ctx)
    raise NotImplementedYet


@season_router.patch(
    "/season-manifest-rows/{row_id}",
    action="season_setup.prepare",
    response_model=SeasonManifestRowOut,
    errors=(409, 501),
)
async def season_row_patch_route(
    row_id: UUID, body: SeasonRowPatchIn, ctx: Ctx, if_match: IfMatch
) -> SeasonManifestRowOut:
    """409 `cohort_approved`; 422 when the person is not eligible (walled, departed, offshore)."""
    await _human(ctx, "season_setup.prepare")
    raise NotImplementedYet


@season_router.post(
    "/season-cohorts/{cohort_id}/rows:exclude",
    action="season_setup.prepare",
    response_model=SeasonManifestRowListOut,
    errors=(409, 501),
)
async def season_rows_exclude_route(
    cohort_id: UUID, body: SeasonRowsExcludeIn, ctx: Ctx, key: IdempotencyKey
) -> SeasonManifestRowListOut:
    await _human(ctx, "season_setup.prepare")
    raise NotImplementedYet


@season_router.post(
    "/season-asks/{ask_id}/answer",
    action="season_setup.prepare",
    response_model=SeasonAskOut,
    errors=(409, 501),
)
async def season_ask_answer_route(
    ask_id: UUID, body: SeasonAskAnswerIn, ctx: Ctx, key: IdempotencyKey
) -> SeasonAskOut:
    """A person's answer, stored with `answered_by`; the planner never answers (INV-1)."""
    await _human(ctx, "season_setup.prepare")
    raise NotImplementedYet


@season_router.post(
    "/season-cohorts/{cohort_id}/approve",
    action="season_setup.approve_cohort",
    response_model=SeasonApprovalOut,
    status_code=201,
    errors=(409, 501),
)
async def season_cohort_approve_route(
    cohort_id: UUID, body: SeasonCohortApproveIn, ctx: Ctx, key: IdempotencyKey
) -> SeasonApprovalOut:
    """Human-only; issues a single-use approval grant (ADR-161). 409 `manifest_superseded` when
    the version moved."""
    await _human(ctx, "season_setup.approve_cohort")
    raise NotImplementedYet


@season_router.post(
    "/season-cohorts/{cohort_id}/withdraw-approval",
    action="season_setup.approve_cohort",
    response_model=SeasonCohortOut,
    errors=(409, 501),
)
async def season_cohort_withdraw_route(
    cohort_id: UUID, body: SeasonCohortWithdrawIn, ctx: Ctx, key: IdempotencyKey
) -> SeasonCohortOut:
    """409 `execution_started` after the first step ran."""
    await _human(ctx, "season_setup.approve_cohort")
    raise NotImplementedYet


@season_router.get(
    f"{_S}/manifests/{{manifest_id}}/export.xlsx",
    action="export.create",
    response_model=bytes,
    errors=(501,),
)
async def season_manifest_export_route(tax_year: int, manifest_id: UUID, ctx: Ctx) -> bytes:
    """Byte-stable, formula-escaped (ADR-320); fresh MFA under `export.create` (AC-8)."""
    await _human(ctx, "export.create")
    raise NotImplementedYet
