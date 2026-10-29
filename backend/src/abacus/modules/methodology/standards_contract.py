"""C21 v1 part B, the stub: firm standards and threshold policies (K-02-T02; K-02 §3 F3-F5, §4.2
to §4.5; KNW-04). Contract: `docs/contracts/rules-tables.md`; screen: `docs/screens/KNW-04.md`.

Per-tenant, versioned numbers and checklists that sort agent output and govern review. Two tables
follow the glossary: `firm_standards` (review checklists, review levels, the return-approval
policy, SSARS & CAS settings) and `threshold_policies` (AJE, variance, materiality, document
confidence); one API serves both, keyed by `kind`. A named partner owns each one and is the only
person who drafts or publishes it (`owner_of_target`, DEC-1150). Every version has an effective
date; "Superseded" is computed at read time, never stored. Drafts are partners' only.

Content is database rows loaded through the import endpoints (AGENTS 16): no standard's value is
a constant here. Nothing in K-02 calls a model (INV-1): every write is a person's, with
`published_actor_kind = 'human'` checked by the database (K-02-T04).

Each route answers 404 for a client principal (INV-4), 403 for a principal the matrix refuses,
404 with `knowledge.firm_standards` off and 501 `not_implemented` with it on until its build
task: reads, lifecycle and examples K-02-T08; import and export K-02-T11.

The deterministic module API (`classify_entry`, `variance_exceeded`, ...) raises
`NotImplementedError` until K-02-T10; its signatures are frozen with C21 (S17). Every result names
the policy version used (INV-2), so consumers can show "Approved by RM under BH AJE thresholds v2".

Classification (ADR-031): standard payloads `internal`; example rows and BH-TAX-02's applies-to
entries `confidential` (client names). No K-02 table holds TRI.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import KNOWLEDGE_FIRM_STANDARDS
from abacus.kernel._statuses import FirmStandardVersionStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    TargetFacts,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

# `firm_standards` kinds and `threshold_policies` kinds (K-02 §4.2, M-B).
FirmStandardKind = Literal[
    "review_checklist", "review_levels", "return_approval_policy", "ssars_cas_settings"
]
ThresholdPolicyKind = Literal[
    "aje_thresholds", "variance_thresholds", "materiality_ranges", "document_confidence"
]
StandardKind = Literal[
    "review_checklist",
    "review_levels",
    "return_approval_policy",
    "ssars_cas_settings",
    "aje_thresholds",
    "variance_thresholds",
    "materiality_ranges",
    "document_confidence",
]
# KNW-04's sections (`?section=`), in the section list's order; `deadline_rules` is section j,
# composed over the platform reference sets (DF-10).
Section = Literal[
    "review_checklists",
    "review_levels",
    "return_approval",
    "aje_thresholds",
    "variance_thresholds",
    "materiality_ranges",
    "document_confidence",
    "ssars_cas",
    "deadline_rules",
]
ReviewLevel = Literal["L1", "L2", "L3", "L4", "L5"]  # DEC-36: the names are fixed
ApproverLevel = Literal["senior_or_above", "manager_or_partner", "partner"]
StandardKey = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{2,79}$")]
Pct = Annotated[Decimal, Field(ge=0, le=100, max_digits=6, decimal_places=3)]
Usd = Annotated[int, Field(ge=0)]  # whole dollars


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- payloads, one per kind (payload_schema_version 1) -------------------------------------------


class AjeThresholdRow(BaseModel):
    """One account class. `limit` rows are within threshold up to `limit_usd`; the last two rows
    of every version ("All other classes · Review required" and "Attest clients · Always held")
    cannot be removed (K-02-T05 validates)."""

    model_config = _frozen()

    account_class: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    rule: Annotated[Literal["limit", "review_required", "always_held"], classified("internal")]
    limit_usd: Annotated[Usd | None, classified("internal")]
    approver_level: Annotated[ApproverLevel, classified("internal")]
    batch: Annotated[bool, classified("internal")]


class AjeThresholdsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["aje_thresholds"], classified("internal")]
    rows: Annotated[
        list[AjeThresholdRow], Field(min_length=2, max_length=50), classified("internal")
    ]


class VarianceRow(BaseModel):
    """A variance is exceeded only when both the percent and the amount are (K-02 §4.3)."""

    model_config = _frozen()

    context: Annotated[
        Literal["close_flux", "ssars_review_analytics", "tax_two_year"], classified("internal")
    ]
    pct: Annotated[Pct, classified("internal")]
    amount_usd: Annotated[Usd, classified("internal")]


class VarianceThresholdsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["variance_thresholds"], classified("internal")]
    rows: Annotated[list[VarianceRow], Field(min_length=1, max_length=10), classified("internal")]


class MaterialityRange(BaseModel):
    model_config = _frozen()

    engagement_kind: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    benchmark: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    low_pct: Annotated[Pct, classified("internal")]
    high_pct: Annotated[Pct, classified("internal")]


class StandardPctRange(BaseModel):
    model_config = _frozen()

    low_pct: Annotated[Pct, classified("internal")]
    high_pct: Annotated[Pct, classified("internal")]


class MaterialityRangesPayload(BaseModel):
    """Decisions stay the engagement partner's: these are the ranges a decision is validated
    against (A-04's AUD-07)."""

    model_config = _frozen()

    kind: Annotated[Literal["materiality_ranges"], classified("internal")]
    rows: Annotated[
        list[MaterialityRange], Field(min_length=1, max_length=20), classified("internal")
    ]
    performance_materiality: Annotated[StandardPctRange, classified("internal")]
    clearly_trivial_pct: Annotated[Pct, classified("internal")]


class DocumentConfidencePayload(BaseModel):
    """`auto_accept_enabled` stays false while the policy principal is dormant (P-08)."""

    model_config = _frozen()

    kind: Annotated[Literal["document_confidence"], classified("internal")]
    hold_below_pct: Annotated[Pct, classified("internal")]
    auto_accept_above_pct: Annotated[Pct, classified("internal")]
    auto_accept_enabled: Annotated[Literal[False], classified("internal")]


class ChecklistAppliesTo(BaseModel):
    model_config = _frozen()

    form: Annotated[str, Field(min_length=1, max_length=20), classified("internal")]
    tax_year: Annotated[int, Field(ge=2000, le=2100), classified("internal")]


class ChecklistItem(BaseModel):
    """Firm-authored text only (ADR-056)."""

    model_config = _frozen()

    key: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,79}$"), classified("internal")]
    section: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    text: Annotated[str, Field(min_length=1, max_length=1000), classified("internal")]


class ReviewChecklistPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["review_checklist"], classified("internal")]
    applies_to: Annotated[ChecklistAppliesTo, classified("internal")]
    items: Annotated[
        list[ChecklistItem], Field(min_length=1, max_length=200), classified("internal")
    ]


class ReviewTier(BaseModel):
    model_config = _frozen()

    tier: Annotated[int, Field(ge=1, le=5), classified("internal")]
    name: Annotated[str, Field(min_length=1, max_length=40), classified("internal")]
    required_levels: Annotated[list[ReviewLevel], Field(min_length=1), classified("internal")]
    second_partner_review: Annotated[bool, classified("internal")]
    criteria: Annotated[str, Field(max_length=500), classified("internal")]


class ReviewLevelsPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["review_levels"], classified("internal")]
    tiers: Annotated[list[ReviewTier], Field(min_length=1, max_length=5), classified("internal")]


class ReturnApprovalAssignment(BaseModel):
    """A client and the partner who gives its final approval (client ids are confidential)."""

    model_config = _frozen()

    client_id: Annotated[UUID, classified("confidential")]
    approver_user_id: Annotated[UUID, classified("internal")]


class ReturnApprovalPolicyPayload(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["return_approval_policy"], classified("internal")]
    code: Annotated[str, Field(pattern=r"^[A-Z0-9-]{2,20}$"), classified("internal")]  # BH-TAX-02
    rule: Annotated[Literal["signing_partner_final_approval"], classified("internal")]
    applies_to: Annotated[
        list[ReturnApprovalAssignment], Field(max_length=2000), classified("confidential")
    ]
    export_condition: Annotated[Literal["after_final_approval"], classified("internal")]


class SsarsCasSettingsPayload(BaseModel):
    """SSARS 27's boundary: periods ending on or after Dec 15, 2026 (K-02 §4.3)."""

    model_config = _frozen()

    kind: Annotated[Literal["ssars_cas_settings"], classified("internal")]
    early_adopt_ssars27: Annotated[bool, classified("internal")]


StandardPayload = Annotated[
    AjeThresholdsPayload
    | VarianceThresholdsPayload
    | MaterialityRangesPayload
    | DocumentConfidencePayload
    | ReviewChecklistPayload
    | ReviewLevelsPayload
    | ReturnApprovalPolicyPayload
    | SsarsCasSettingsPayload,
    Field(discriminator="kind"),
]


# --- reads ---------------------------------------------------------------------------------------


class StandardPersonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]


class StandardVersionSummaryOut(BaseModel):
    """A version on the header and the Timeline. `status` is the C2 code: `superseded` is
    computed (a later published version is in effect)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    status: Annotated[FirmStandardVersionStatus, classified("internal")]
    effective_from: Annotated[date | None, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]
    published_by: Annotated[StandardPersonOut | None, classified("internal")]
    # INV-5: a person, never the agent; "via Agent" never appears on a standard.
    current: Annotated[bool, classified("internal")]
    # K-02-T13 (additive): a checklist version's `applies_to.tax_year` ("1040 Review Checklist v7
    # (TY2026)"); null for other kinds.
    tax_year: Annotated[int | None, classified("internal")] = None


class StandardOut(BaseModel):
    """A section row: the standard, its owner, the version in effect, and the partner-only draft
    (absent for anyone else). `allowed_actions` drives New version…, Publish and Import."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[StandardKind, classified("internal")]
    key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("internal")]
    owner: Annotated[StandardPersonOut, classified("internal")]
    current_version: Annotated[StandardVersionSummaryOut | None, classified("internal")]
    draft_version: Annotated[StandardVersionSummaryOut | None, classified("internal")]
    # KNW-04 b's "Applied to" (a registered usage counter's count over `visible()`; null when
    # none is registered, never an invented number).
    usage_count: Annotated[int | None, classified("internal")]
    # K-02-T13 (additive): how many entries the version in effect holds (a checklist's checks,
    # KNW-04 b's "Checks"); null with no version in effect.
    entries: Annotated[int | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")]


class StandardVersionOut(BaseModel):
    """One version in full."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    standard_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    status: Annotated[FirmStandardVersionStatus, classified("internal")]
    effective_from: Annotated[date | None, classified("internal")]
    payload_schema_version: Annotated[int, classified("internal")]
    payload_hash: Annotated[str, classified("internal")]
    change_summary: Annotated[str | None, classified("internal")]
    drafted_from_version_id: Annotated[UUID | None, classified("internal")]
    drafted_by: Annotated[StandardPersonOut, classified("internal")]
    published_by: Annotated[StandardPersonOut | None, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]
    # The If-Match value for PATCH (409 `stale_version` when it moved; the repo's code, DEC-1151).
    row_version: Annotated[int, classified("internal")]
    payload: Annotated[StandardPayload, classified("internal")]


class StandardDetailOut(BaseModel):
    """KNW-04's form pane: the standard, the version shown, and the Timeline (newest first)."""

    model_config = ConfigDict(frozen=True)

    standard: Annotated[StandardOut, classified("internal")]
    version: Annotated[StandardVersionOut | None, classified("internal")]
    timeline: Annotated[list[StandardVersionSummaryOut], classified("internal")]
    # K-02-T13 (additive): display names for the ids the payload holds (BH-TAX-02's clients and
    # approvers), `visible()`-filtered: a walled client's id is absent, and so is its row.
    labels: Annotated[dict[str, str], classified("confidential")] = Field(default_factory=dict)


class StandardChangedCellOut(BaseModel):
    """One changed value for KNW-04 i: the amber cell with the struck prior value. `path` is a
    JSON pointer into the payload; values are rendered strings."""

    model_config = ConfigDict(frozen=True)

    path: Annotated[str, classified("internal")]
    before: Annotated[str | None, classified("internal")]
    after: Annotated[str | None, classified("internal")]


class StandardVersionDiffOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    against_version_id: Annotated[UUID, classified("internal")]
    cells: Annotated[list[StandardChangedCellOut], classified("internal")]


class StandardExampleRowOut(BaseModel):
    """One example a registered provider gives (KNW-04 a, e, f, g, h), filtered by `visible()`
    with no hidden counts (DEC-43): a walled client's row is absent and totals are recomputed."""

    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID | None, classified("confidential")]
    client_name: Annotated[str | None, classified("confidential")]
    label: Annotated[str, classified("confidential")]
    amount_usd: Annotated[int | None, classified("confidential")]
    outcome: Annotated[str, classified("internal")]
    detail: Annotated[str | None, classified("confidential")]
    route: Annotated[str | None, classified("internal")]
    # K-02-T13 (additive): who decided the row ("approved as one batch by Raj Malhotra"); never
    # the agent (INV-5).
    approver_name: Annotated[str | None, classified("confidential")] = None
    # K-02-T13 (additive): a provider's further columns, rendered as given (materiality's
    # `performance` and `clearly_trivial`, a decision's `decided_at`).
    cells: Annotated[dict[str, str], classified("confidential")] = Field(default_factory=dict)


class StandardExamplesOut(BaseModel):
    """`provider_registered` false: KNW-04's designed empty state, never invented rows."""

    model_config = ConfigDict(frozen=True)

    standard_id: Annotated[UUID, classified("internal")]
    period: Annotated[str | None, classified("internal")]
    provider_registered: Annotated[bool, classified("internal")]
    # K-02-T13 (additive): the provider's one-line heading ("1065 Review Checklist v4 · last run
    # started 9:18 AM · Samuel Ito").
    caption: Annotated[str | None, classified("confidential")] = None
    rows: Annotated[list[StandardExampleRowOut], classified("confidential")]


class StandardImportProblemOut(BaseModel):
    """A workbook problem: where, and a fixed code, never the cell's content (ADR-052)."""

    model_config = ConfigDict(frozen=True)

    sheet: Annotated[str, classified("internal")]
    row: Annotated[int | None, classified("internal")]
    column: Annotated[str | None, classified("internal")]
    code: Annotated[str, classified("internal")]


class StandardImportResultOut(BaseModel):
    """An import makes drafts; it never publishes."""

    model_config = ConfigDict(frozen=True)

    drafts: Annotated[list[StandardVersionSummaryOut], classified("internal")]
    problems: Annotated[list[StandardImportProblemOut], classified("internal")]


# --- writes --------------------------------------------------------------------------------------


class StandardCreateIn(BaseModel):
    model_config = _frozen()

    kind: Annotated[StandardKind, classified("internal")]
    key: Annotated[StandardKey, classified("internal")]
    name: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    owner_id: Annotated[UUID, classified("internal")]


class StandardOwnerIn(BaseModel):
    model_config = _frozen()

    owner_id: Annotated[UUID, classified("internal")]


class StandardDraftPatchIn(BaseModel):
    model_config = _frozen()

    payload: Annotated[StandardPayload, classified("internal")]
    change_summary: Annotated[str | None, Field(max_length=500), classified("internal")] = None


class StandardPublishIn(BaseModel):
    """`effective_from` on or after today (business time) and after the current version's."""

    model_config = _frozen()

    effective_from: Annotated[date, classified("internal")]
    change_summary: Annotated[str, Field(min_length=1, max_length=500), classified("internal")]


class StandardImportIn(BaseModel):
    """A workbook already uploaded and scanned through the upload flow (an upload intent)."""

    model_config = _frozen()

    upload_id: Annotated[UUID, classified("internal")]


standards_router = AbacusRouter(prefix="/v1/standards", tags=["standards"])
StandardId = Annotated[UUID, Path()]
VersionId = Annotated[UUID, Path()]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]


_OWNER_ACTIONS = frozenset({"firm_standard.draft", "firm_standard.publish"})


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """INV-4: a client principal gets 404. Then the matrix (403), the flag (404), then 501.
    Until K-02-T08 reads the standard, the owner-conditioned actions are checked as if the actor
    owned it: a person who is not a partner member is still refused; the owner check proper
    (403 `not_standard_owner`) comes with the service."""
    if ctx.client:
        raise NotFound("firm_standard")
    resource = Resource.firm(ctx.tenant_id)
    if action in _OWNER_ACTIONS:
        resource = replace(resource, target=TargetFacts(owner_user_id=ctx.user_id))
    await authorise(ctx, action, resource)
    if not await flag_enabled(ctx.tenant, KNOWLEDGE_FIRM_STANDARDS):
        raise NotFound(KNOWLEDGE_FIRM_STANDARDS.name)
    raise NotImplementedYet


@standards_router.get(
    "", action="firm_standard.read", response_model=ListPage[StandardOut], errors=(501,)
)
async def list_standards_route(
    ctx: Ctx, kind: Annotated[StandardKind | None, Query()] = None
) -> ListPage[StandardOut]:
    """KNW-04's section list and rows; drafts appear for partners only."""
    await _stub(ctx, "firm_standard.read")


@standards_router.post(
    "",
    action="firm_standard.create",
    response_model=StandardOut,
    status_code=201,
    errors=(409, 501),
)
async def create_standard_route(body: StandardCreateIn, ctx: Ctx) -> StandardOut:
    """Create a standard (QM owner or practice leader, fresh MFA); the owner must be a partner
    member (422 `owner_not_partner`)."""
    await _stub(ctx, "firm_standard.create")


@standards_router.get(
    "/{standard_id}", action="firm_standard.read", response_model=StandardDetailOut, errors=(501,)
)
async def standard_route(
    standard_id: StandardId, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> StandardDetailOut:
    """The form pane: the version in effect (or `?version=`) and the Timeline."""
    await _stub(ctx, "firm_standard.read")


@standards_router.put(
    "/{standard_id}/owner",
    action="firm_standard.assign_owner",
    response_model=StandardOut,
    errors=(501,),
)
async def assign_owner_route(
    standard_id: StandardId, body: StandardOwnerIn, ctx: Ctx
) -> StandardOut:
    """Assign the owner (a partner member; 422 `owner_not_partner`)."""
    await _stub(ctx, "firm_standard.assign_owner")


@standards_router.get(
    "/{standard_id}/versions/{version_id}",
    action="firm_standard.read",
    response_model=StandardVersionOut,
    errors=(501,),
)
async def standard_version_route(
    standard_id: StandardId, version_id: VersionId, ctx: Ctx
) -> StandardVersionOut:
    """One version; a draft is 404 for anyone but a partner (US-3.4)."""
    await _stub(ctx, "firm_standard.read")


@standards_router.post(
    "/{standard_id}/versions",
    action="firm_standard.draft",
    response_model=StandardVersionOut,
    status_code=201,
    errors=(409, 501),
)
async def draft_version_route(standard_id: StandardId, ctx: Ctx) -> StandardVersionOut:
    """New version…: a draft from the current version (409 `draft_exists`; 403
    `not_standard_owner` for anyone but the owner)."""
    await _stub(ctx, "firm_standard.draft")


@standards_router.patch(
    "/{standard_id}/versions/{version_id}",
    action="firm_standard.draft",
    response_model=StandardVersionOut,
    errors=(409, 501),
)
async def edit_draft_route(
    standard_id: StandardId,
    version_id: VersionId,
    body: StandardDraftPatchIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> StandardVersionOut:
    """Edit the draft (409 `stale_version` or `not_draft`, 422 `payload_invalid`)."""
    await _stub(ctx, "firm_standard.draft")


@standards_router.delete(
    "/{standard_id}/versions/{version_id}",
    action="firm_standard.draft",
    response_model=StandardVersionSummaryOut,
    errors=(409, 501),
)
async def discard_draft_route(
    standard_id: StandardId, version_id: VersionId, ctx: Ctx, if_match: IfMatch
) -> StandardVersionSummaryOut:
    """Discard draft: status `discarded`; the row stays (never deleted)."""
    await _stub(ctx, "firm_standard.draft")


@standards_router.post(
    "/{standard_id}/versions/{version_id}/publish",
    action="firm_standard.publish",
    response_model=StandardVersionOut,
    errors=(409, 501),
)
async def publish_version_route(
    standard_id: StandardId,
    version_id: VersionId,
    body: StandardPublishIn,
    ctx: Ctx,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
) -> StandardVersionOut:
    """Publish vN…: the owner, a person, with fresh MFA (422 `effective_from_backdated`,
    `effective_from_not_after_current`)."""
    await _stub(ctx, "firm_standard.publish")


@standards_router.get(
    "/{standard_id}/versions/{version_id}/diff",
    action="firm_standard.read",
    response_model=StandardVersionDiffOut,
    errors=(501,),
)
async def version_diff_route(
    standard_id: StandardId,
    version_id: VersionId,
    ctx: Ctx,
    against: Annotated[UUID | None, Query()] = None,
) -> StandardVersionDiffOut:
    """Cell-level diff for KNW-04 i, against the version the draft came from by default."""
    await _stub(ctx, "firm_standard.read")


@standards_router.get(
    "/{standard_id}/versions/{version_id}/export.xlsx",
    action="firm_standard.read",
    response_model=bytes,
    errors=(501,),
)
async def export_version_route(standard_id: StandardId, version_id: VersionId, ctx: Ctx) -> bytes:
    """The version as a workbook; re-importing it gives an empty diff (US-5.1)."""
    await _stub(ctx, "firm_standard.read")


@standards_router.get(
    "/{standard_id}/examples",
    action="firm_standard.read",
    response_model=StandardExamplesOut,
    errors=(501,),
)
async def standard_examples_route(
    standard_id: StandardId,
    ctx: Ctx,
    period: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> StandardExamplesOut:
    """Registered example providers' rows, `visible()`-filtered with no hidden counts."""
    await _stub(ctx, "firm_standard.read")


@standards_router.post(
    "/{standard_id}/imports",
    action="firm_standard.import",
    response_model=StandardImportResultOut,
    status_code=201,
    errors=(501,),
)
async def import_standard_route(
    standard_id: StandardId, body: StandardImportIn, ctx: Ctx
) -> StandardImportResultOut:
    """A workbook to a draft of this standard (its owner's; 422 `import_invalid` with
    problems). Never publishes."""
    await _stub(ctx, "firm_standard.import")


@standards_router.post(
    "/imports",
    action="firm_standard.import",
    response_model=StandardImportResultOut,
    status_code=201,
    errors=(501,),
)
async def import_standards_route(body: StandardImportIn, ctx: Ctx) -> StandardImportResultOut:
    """Onboarding: one sheet per kind, one draft per standard; an owner who is not a partner
    member is a row problem (`owner_not_partner`)."""
    await _stub(ctx, "firm_standard.import")


# --- C21 part B module API (frozen S17; K-02-T08 and T10 implement) ------------------------------

EntryOutcome = Literal["within_threshold", "review_required"]


@dataclass(frozen=True)
class PolicyRef:
    """The policy version a result came from (INV-2): consumers store `version_id`."""

    standard_key: str
    version_id: UUID
    version: int
    name: str


@dataclass(frozen=True)
class EntryClassification:
    outcome: EntryOutcome
    # `attest_client`, `over_limit`, `unlisted_class` or None when within threshold.
    reason: str | None
    approver_level: ApproverLevel
    batch: bool
    policy: PolicyRef


@dataclass(frozen=True)
class VarianceResult:
    exceeded: bool
    pct_change: Decimal | None
    amount_change_usd: int
    policy: PolicyRef


@dataclass(frozen=True)
class MaterialityRangeFor:
    engagement_kind: str
    benchmark: str
    low_pct: Decimal
    high_pct: Decimal
    performance_materiality: tuple[Decimal, Decimal]
    clearly_trivial_pct: Decimal
    policy: PolicyRef


@dataclass(frozen=True)
class MaterialityCheck:
    within_range: bool
    performance_within_range: bool
    clearly_trivial_matches: bool
    policy: PolicyRef


@dataclass(frozen=True)
class ConfidenceDecision:
    hold: bool
    auto_accept: bool
    policy: PolicyRef


@dataclass(frozen=True)
class RequiredLevels:
    tier: int
    levels: tuple[ReviewLevel, ...]
    second_partner_review: bool
    policy: PolicyRef


@dataclass(frozen=True)
class ReturnApproval:
    code: str
    approver_user_id: UUID | None
    export_after_final_approval: bool
    policy: PolicyRef


@dataclass(frozen=True)
class SsarsFramework:
    # AR-C 70 preparation before SSARS 27 (periods ending before Dec 15, 2026, unless adopted
    # early); a CAS by-product with no SSARS report or legend after.
    framework: Literal["ar_c_70_preparation", "cas_by_product"]
    policy: PolicyRef


@dataclass(frozen=True)
class ExampleRow:
    client_id: UUID | None
    client_name: str | None
    label: str
    amount_usd: int | None
    outcome: str
    detail: str | None
    route: str | None


# A consumer's examples for a standard kind (C-01 for AJE thresholds, A-04 for materiality):
# (viewer, period) -> rows, already filtered by `visible()`.
ExamplesProvider = Callable[[AuthContext, str | None], Awaitable[list[ExampleRow]]]


def _unbuilt(task: str) -> NoReturn:
    raise NotImplementedError(f"C21 part B: {task} builds this")


async def current_version(tenant_id: UUID, standard_key: str, as_of: date) -> PolicyRef:
    """The version of a standard in effect on `as_of` (its latest published `effective_from` on
    or before it). None published by then: `LookupError`."""
    _unbuilt("K-02-T08")


def classify_entry(
    payload: AjeThresholdsPayload,
    policy: PolicyRef,
    *,
    account_class: str,
    amount_usd: int,
    attest_client: bool,
) -> EntryClassification:
    """An AJE's outcome under a thresholds version: an attest client's entry is always held."""
    _unbuilt("K-02-T10")


def variance_exceeded(
    payload: VarianceThresholdsPayload,
    policy: PolicyRef,
    *,
    context: str,
    current_usd: int,
    prior_usd: int,
) -> VarianceResult:
    """Exceeded only when both the percent and the amount are."""
    _unbuilt("K-02-T10")


def materiality_range_for(
    payload: MaterialityRangesPayload, policy: PolicyRef, *, engagement_kind: str
) -> MaterialityRangeFor:
    _unbuilt("K-02-T10")


def validate_materiality(
    payload: MaterialityRangesPayload,
    policy: PolicyRef,
    *,
    engagement_kind: str,
    pct: Decimal,
    performance_pct: Decimal,
    clearly_trivial_pct: Decimal,
) -> MaterialityCheck:
    _unbuilt("K-02-T10")


def confidence_hold(
    payload: DocumentConfidencePayload, policy: PolicyRef, *, confidence_pct: Decimal
) -> ConfidenceDecision:
    _unbuilt("K-02-T10")


def required_review_levels(
    payload: ReviewLevelsPayload, policy: PolicyRef, *, tier: int
) -> RequiredLevels:
    _unbuilt("K-02-T10")


def return_approval_policy(
    payload: ReturnApprovalPolicyPayload, policy: PolicyRef, *, client_id: UUID
) -> ReturnApproval:
    _unbuilt("K-02-T10")


def ssars_framework_for(
    payload: SsarsCasSettingsPayload, policy: PolicyRef, *, period_end: date
) -> SsarsFramework:
    _unbuilt("K-02-T10")


def register_standard_examples(kind: StandardKind, provider: ExamplesProvider) -> None:
    """A consumer's example rows for KNW-04 (K-02-T08 builds the slot)."""
    _unbuilt("K-02-T08")
