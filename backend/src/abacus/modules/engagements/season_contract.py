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
from typing import Annotated, Literal, cast
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
    approver: Annotated[SeasonPersonOut | None, Confidential] = None
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
    answered_by: Annotated[SeasonPersonOut | None, Confidential] = None


class SeasonManifestOut(BaseModel):
    model_config = _cfg()

    manifest_id: Annotated[UUID, Internal]
    season_id: Annotated[UUID, Internal]
    tax_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    version: Annotated[int, Field(ge=1), Internal]
    status: Annotated[Literal["building", "ready", "superseded"], Internal]
    built_by: Annotated[SeasonPersonOut | None, Confidential] = None
    built_at: Annotated[datetime | None, Internal] = None
    inputs_hash: Hash
    tally: Annotated[SeasonTallyOut, Internal]
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
    preparer: Annotated[SeasonPersonOut | None, Confidential] = None
    reviewer: Annotated[SeasonPersonOut | None, Confidential] = None
    signer: Annotated[SeasonPersonOut | None, Confidential] = None
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
    approved_by: Annotated[SeasonPersonOut, Confidential]
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


async def _people(ids: set[UUID]) -> dict[UUID, SeasonPersonOut]:
    from abacus.modules.identity.api import names_of

    names = await names_of(sorted(ids, key=str)) if ids else {}

    def initials(name: str) -> str:
        return "".join(p[0] for p in name.split()[:2]).upper() or "?"

    return {
        u: SeasonPersonOut(user_id=u, initials=initials(n), name=n[:120]) for u, n in names.items()
    }


def _row_out(r: object, people: dict[UUID, SeasonPersonOut]) -> SeasonManifestRowOut:
    from abacus.modules.engagements.season_service import RowView

    v = cast(RowView, r)

    def who(u: UUID | None) -> SeasonPersonOut | None:
        return None if u is None else people.get(u)

    binder = f"{v.binders} binder" + ("s" if v.binders != 1 else "")
    return SeasonManifestRowOut(
        row_id=v.row_id,
        cohort_id=v.cohort_id,
        client_id=v.client_id,
        client_name=v.client_name[:200],
        forms=list(v.forms),
        preparer=who(v.preparer_user_id),
        reviewer=who(v.reviewer_user_id),
        signer=who(v.signer_user_id),
        binder_summary=binder,
        request_count=v.requests,
        letter_kind=cast(Literal["renewal", "new", "none"], v.letter_kind),
        fee_change_pct=v.fee_change_pct,
        consent_purposes=list(v.consent_purposes),
        signers=1 if v.signer_user_id is not None else 0,
        invitees=[],
        exception_codes=[cast(ExceptionCode, c) for c in v.exception_codes],
        display=cast(RowDisplay, v.display),
        row_version=v.row_version,
    )


def _cohort_out(c: object, people: dict[UUID, SeasonPersonOut]) -> SeasonCohortOut:
    from abacus.modules.engagements.season_service import CohortView

    v = cast(CohortView, c)
    return SeasonCohortOut(
        cohort_id=v.cohort_id,
        position=v.position,
        office_id=v.office_id,
        office_name=v.office_name[:80],
        segment=cast(Segment, v.segment),
        status=cast(CohortStatus, v.status),
        display=cast(CohortDisplay, v.display),
        engagements=v.engagements,
        returns=v.returns,
        binders=v.binders,
        letters=v.letters,
        invitations=v.invitations,
        exceptions=v.exceptions,
        approver=None if v.approver_user_id is None else people.get(v.approver_user_id),
        created_rows=v.created,
        rows_hash=v.rows_hash,
    )


async def _manifest_out(ctx: AuthContext, tax_year: int, manifest_id: UUID) -> SeasonManifestOut:
    from abacus.modules.engagements.season_service import manifest

    m = await manifest(ctx, tax_year, manifest_id)
    ids = {m.built_by} | {c.approver_user_id for c in m.cohorts if c.approver_user_id}
    people = await _people(ids)
    cohorts = [_cohort_out(c, people) for c in m.cohorts]
    offices: dict[UUID, tuple[str, int]] = {}
    for c in m.cohorts:
        name, n = offices.get(c.office_id, (c.office_name, 0))
        offices[c.office_id] = (name, n + c.returns)
    return SeasonManifestOut(
        manifest_id=m.manifest_id,
        season_id=m.season_id,
        tax_year=m.tax_year,
        version=m.version,
        status=cast(Literal["building", "ready", "superseded"], m.status),
        built_by=people.get(m.built_by),
        built_at=m.built_at,
        inputs_hash=m.inputs_hash,
        tally=SeasonTallyOut(
            engagements=sum(c.engagements for c in cohorts),
            returns=sum(c.returns for c in cohorts),
            binders=sum(c.binders for c in cohorts),
            created=sum(c.created_rows for c in cohorts),
            cohorts_approved=sum(1 for c in cohorts if c.status != "draft"),
            cohorts=len(cohorts),
            exceptions=sum(c.exceptions for c in cohorts),
        ),
        offices=[
            SeasonOfficeFootingOut(office_id=o, office_name=name[:80], returns=n)
            for o, (name, n) in offices.items()
        ],
        cohorts=cohorts,
        planner_available=False,
    )


@season_router.get("/seasons", action="season.read", response_model=SeasonListOut, errors=(501,))
async def seasons_route(ctx: Ctx) -> SeasonListOut:
    await _on(ctx)
    from abacus.modules.engagements.season_service import manifests

    return SeasonListOut(
        items=[
            SeasonOut(season_id=s, tax_year=y, manifest_id=m, opened_at=at)
            for s, y, m, at in await manifests(ctx)
        ]
    )


@season_router.get(
    f"{_S}/manifests/{{manifest_id}}",
    action="season.read",
    response_model=SeasonManifestOut,
    errors=(501,),
)
async def season_manifest_route(tax_year: int, manifest_id: UUID, ctx: Ctx) -> SeasonManifestOut:
    await _on(ctx)
    return await _manifest_out(ctx, tax_year, manifest_id)


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
    a rebuild would replace an approved cohort; `no_candidate_source` without a source. The
    planner step (asks) follows its capability task: `planner_available` reads false."""
    await _human(ctx, "season_setup.prepare")
    from abacus.modules.engagements.season_service import build_manifest

    made = await build_manifest(ctx, tax_year, rebuild=body.rebuild)
    return await _manifest_out(ctx, tax_year, made)


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
    from abacus.modules.engagements.season_service import cohort

    found = await cohort(ctx, cohort_id)
    rows = [
        r for r in found.rows
        if (not exceptions_only or r.exception_codes)
        and (q is None or q.lower() in r.client_name.lower())
    ]  # fmt: skip
    ids = {u for r in rows for u in (r.preparer_user_id, r.reviewer_user_id, r.signer_user_id)}
    people = await _people({u for u in ids if u is not None})
    return SeasonManifestRowListOut(items=[_row_out(r, people) for r in rows], total=len(rows))


@season_router.patch(
    "/season-manifest-rows/{row_id}",
    action="season_setup.prepare",
    response_model=SeasonManifestRowOut,
    errors=(409, 501),
)
async def season_row_patch_route(
    row_id: UUID, body: SeasonRowPatchIn, ctx: Ctx, if_match: IfMatch
) -> SeasonManifestRowOut:
    """409 `cohort_approved`; 409 `assignee_not_eligible` when the person is not an active member
    or is walled from the client; If-Match is the row version seen (409 `stale_version`)."""
    await _human(ctx, "season_setup.prepare")
    from abacus.modules.engagements.season_service import reassign, row

    if not if_match.isdigit():
        raise NotFound("season_manifest_row")
    await reassign(
        ctx, row_id, int(if_match), preparer=body.preparer_user_id,
        reviewer=body.reviewer_user_id, signer=body.signer_user_id,
    )  # fmt: skip
    found = await row(ctx, row_id)
    ids = {found.preparer_user_id, found.reviewer_user_id, found.signer_user_id}
    return _row_out(found, await _people({u for u in ids if u is not None}))


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
    from abacus.modules.engagements.season_service import cohort, exclude

    mine = {r.row_id for r in (await cohort(ctx, cohort_id)).rows}
    if not set(body.row_ids) <= mine:
        raise NotFound("season_manifest_row")
    await exclude(ctx, body.row_ids, body.reason)
    found = await cohort(ctx, cohort_id)
    ids = {
        u for r in found.rows for u in (r.preparer_user_id, r.reviewer_user_id, r.signer_user_id)
    }
    people = await _people({u for u in ids if u is not None})
    return SeasonManifestRowListOut(
        items=[_row_out(r, people) for r in found.rows], total=len(found.rows)
    )


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
    """Human-only; issues a single-use approval grant (ADR-161) pinning the rows hash and manifest
    version seen (409 `stale_version` when either moved; `rows_hidden` when the approver is
    walled from a row; `cohort_approved` when not a draft), then starts the execution."""
    await _human(ctx, "season_setup.approve_cohort")
    from abacus.modules.engagements.season_execution_service import approve_cohort

    made = await approve_cohort(
        ctx, cohort_id, rows_hash=body.rows_hash, manifest_version=body.manifest_version
    )
    people = await _people({made.approved_by})
    return SeasonApprovalOut(
        approval_id=made.approval_id,
        cohort_id=made.cohort_id,
        approval_grant_id=made.grant_id,
        approved_by=people[made.approved_by],
        approved_at=cast(datetime, made.approved_at),
    )


@season_router.post(
    "/season-cohorts/{cohort_id}/withdraw-approval",
    action="season_setup.approve_cohort",
    response_model=SeasonCohortOut,
    errors=(409, 501),
)
async def season_cohort_withdraw_route(
    cohort_id: UUID, body: SeasonCohortWithdrawIn, ctx: Ctx, key: IdempotencyKey
) -> SeasonCohortOut:
    """409 `execution_started` after the first step ran; the grant is voided."""
    await _human(ctx, "season_setup.approve_cohort")
    from abacus.modules.engagements.season_execution_service import withdraw_cohort
    from abacus.modules.engagements.season_service import cohort

    await withdraw_cohort(ctx, cohort_id, body.reason)
    return _cohort_out(await cohort(ctx, cohort_id), {})


@season_router.get(
    f"{_S}/manifests/{{manifest_id}}/export.xlsx",
    action="export.create",
    response_model=bytes,
    errors=(501,),
)
async def season_manifest_export_route(tax_year: int, manifest_id: UUID, ctx: Ctx) -> bytes:
    """Byte-stable, formula-escaped (ADR-320); fresh MFA under `export.create` (AC-8)."""
    await _human(ctx, "export.create")
    from abacus.modules.engagements.season_service import export_xlsx

    return await export_xlsx(ctx, tax_year, manifest_id)
