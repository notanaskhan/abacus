"""C21 v1 part B, the contract: firm standards and threshold policies (K-02-T02; K-02 §3 F3-F5,
§4.2 to §4.5; KNW-04). Contract: `docs/contracts/rules-tables.md`; screen:
`docs/screens/KNW-04.md`.

Per-tenant, versioned numbers and checklists that sort agent output and govern review. Two tables
follow the glossary: `firm_standards` (review checklists, review levels, the return-approval
policy, SSARS & CAS settings) and `threshold_policies` (AJE, variance, materiality, document
confidence); one API serves both, keyed by `kind`. A named partner owns each one and is the only
person who drafts or publishes it (`owner_of_target`, DEC-1150). Every version has an effective
date; "Superseded" is computed at read time, never stored. Drafts are partners' only.

Content is database rows loaded through the import endpoints (AGENTS 16): no standard's value is
a constant here. Nothing in K-02 calls a model (INV-1): every write is a person's, with
`published_actor_kind = 'human'` checked by the database (K-02-T04).

The routes live in `standards_routes.py` and the service in `standards.py` (K-02-T08: reads,
lifecycle and examples); import and export stay 501 until K-02-T11.

The deterministic module API (`classify_entry`, `variance_exceeded`, ...) raises
`NotImplementedError` until K-02-T10; its signatures are frozen with C21 (S17). Every result names
the policy version used (INV-2), so consumers can show "Approved by RM under BH AJE thresholds v2".

Classification (ADR-031): standard payloads `internal`; example rows and BH-TAX-02's applies-to
entries `confidential` (client names). No K-02 table holds TRI.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import FirmStandardVersionStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainInvalid
from abacus.modules.identity.api import AuthContext

# `firm_standards` kinds and `threshold_policies` kinds (K-02 §4.2, M-B).
FirmStandardKind = Literal[
    "review_checklist", "review_levels", "return_approval_policy", "ssars_cas_settings"
]
ThresholdPolicyKind = Literal[
    "aje_thresholds",
    "variance_thresholds",
    "materiality_ranges",
    "document_confidence",
    "attribute_sample_sizes",  # A-03-T10 (ADR-340 §6): the firm's attribute sample size table
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
    "attribute_sample_sizes",
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

# The stored codes plus C2's derived `superseded` (a later published version is in effect; the
# registry marks it derived, so the generated enum leaves it out). K-02-T08.
VersionShownStatus = FirmStandardVersionStatus | Literal["superseded"]


class AjeThresholdRow(BaseModel):
    """One account class. `limit` rows are within threshold up to `limit_usd`; the last two rows
    of every version ("All other classes · Review required" and "Attest clients · Always held")
    cannot be removed (K-02-T05 validates)."""

    model_config = _frozen()

    account_class: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    rule: Annotated[Literal["limit", "review_required", "always_held"], classified("internal")]
    # K-02-T18: an empty workbook cell reads as absent, so the null limit is the default.
    limit_usd: Annotated[Usd | None, classified("internal")] = None
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
    # Empty by default: an exported empty cell imports back as "" (K-02-T11 round trip).
    criteria: Annotated[str, Field(max_length=500), classified("internal")] = ""


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


Rmm = Literal["low", "moderate", "high"]


class AttributeSizeRow(BaseModel):
    """One row of the size table: the sample size for a risk of material misstatement and a
    tolerable and expected deviation rate, at the table's confidence."""

    model_config = _frozen()

    rmm: Annotated[Rmm, classified("internal")]
    tolerable_pct: Annotated[Pct, classified("internal")]
    expected_pct: Annotated[Pct, classified("internal")]
    size: Annotated[int, Field(ge=1, le=10_000), classified("internal")]


class AttributeSampleSizesPayload(BaseModel):
    """A-03-T10 (ADR-340 §6; A-03 §4.1): the firm's attribute sample sizes ("BH-EBP-210 Table
    2"). Firm content, loaded through the import; sampling reads it through `methodology.api`
    and computes the statistical cross-check beside it."""

    model_config = _frozen()

    kind: Annotated[Literal["attribute_sample_sizes"], classified("internal")]
    confidence_pct: Annotated[Pct, classified("internal")]
    rows: Annotated[
        list[AttributeSizeRow], Field(min_length=1, max_length=200), classified("internal")
    ]


StandardPayload = Annotated[
    AjeThresholdsPayload
    | VarianceThresholdsPayload
    | MaterialityRangesPayload
    | DocumentConfidencePayload
    | AttributeSampleSizesPayload
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
    status: Annotated[VersionShownStatus, classified("internal")]
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
    status: Annotated[VersionShownStatus, classified("internal")]
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


# --- C21 part B module API (frozen S17; `standards.py` builds current_version and the examples
# slot, K-02-T08; K-02-T10 the deterministic functions) ----------------------------------------

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
class AttributeSize:
    """A-03-T10: the size the firm's table gives, with the version it came from (the citation)."""

    size: int
    confidence_pct: Decimal
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


SSARS27_BOUNDARY: Final = date(2026, 12, 15)


class StandardRowMissing(DomainInvalid):
    """The policy version has no row for what was asked (an engagement kind, a tier, a
    context): a consumer asked a question the firm's standard does not answer."""

    code = "standard_row_missing"


def _row_for[T](rows: Sequence[T], match: Callable[[T], bool], what: str) -> T:
    for row in rows:
        if match(row):
            return row
    raise StandardRowMissing(facts={"missing": what})


def classify_entry(
    payload: AjeThresholdsPayload,
    policy: PolicyRef,
    *,
    account_class: str,
    amount_usd: int,
    attest_client: bool,
) -> EntryClassification:
    """An AJE's outcome under a thresholds version (K-02 §4.3, K-02-T10): an attest client's
    entry is always held whatever the amount; a listed class is within threshold up to its limit
    (inclusive) and review required above it; an unlisted class is review required."""
    amount = abs(amount_usd)
    if attest_client:
        row = _row_for(payload.rows, lambda r: r.rule == "always_held", "always_held")
        return EntryClassification(
            "review_required", "attest_client", row.approver_level, row.batch, policy
        )
    listed = next(
        (r for r in payload.rows if r.rule == "limit" and r.account_class == account_class), None
    )
    if listed is not None and listed.limit_usd is not None:
        if amount <= listed.limit_usd:
            return EntryClassification(
                "within_threshold", None, listed.approver_level, listed.batch, policy
            )
        other = _row_for(payload.rows, lambda r: r.rule == "review_required", "review_required")
        return EntryClassification(
            "review_required", "over_limit", other.approver_level, other.batch, policy
        )
    other = _row_for(payload.rows, lambda r: r.rule == "review_required", "review_required")
    return EntryClassification(
        "review_required", "unlisted_class", other.approver_level, other.batch, policy
    )


def variance_exceeded(
    payload: VarianceThresholdsPayload,
    policy: PolicyRef,
    *,
    context: str,
    current_usd: int,
    prior_usd: int,
) -> VarianceResult:
    """Exceeded only when both the percent and the amount are (strictly over each threshold).
    A prior of zero has no percent change; then the amount alone decides."""
    row = _row_for(payload.rows, lambda r: r.context == context, f"variance:{context}")
    amount = abs(current_usd - prior_usd)
    pct = (
        None
        if prior_usd == 0
        else (Decimal(amount) * 100 / Decimal(abs(prior_usd))).quantize(Decimal("0.001"))
    )
    over_pct = pct is None or pct > row.pct
    return VarianceResult(over_pct and amount > row.amount_usd, pct, amount, policy)


def materiality_range_for(
    payload: MaterialityRangesPayload, policy: PolicyRef, *, engagement_kind: str
) -> MaterialityRangeFor:
    """The firm's range for an engagement kind (the partner decides within it, AUD-07)."""
    row = _row_for(
        payload.rows,
        lambda r: r.engagement_kind == engagement_kind,
        f"materiality:{engagement_kind}",
    )
    pm = payload.performance_materiality
    return MaterialityRangeFor(
        row.engagement_kind,
        row.benchmark,
        row.low_pct,
        row.high_pct,
        (pm.low_pct, pm.high_pct),
        payload.clearly_trivial_pct,
        policy,
    )


def validate_materiality(
    payload: MaterialityRangesPayload,
    policy: PolicyRef,
    *,
    engagement_kind: str,
    pct: Decimal,
    performance_pct: Decimal,
    clearly_trivial_pct: Decimal,
) -> MaterialityCheck:
    """Whether a partner's chosen percentages sit inside the firm's ranges (inclusive)."""
    found = materiality_range_for(payload, policy, engagement_kind=engagement_kind)
    low, high = found.performance_materiality
    return MaterialityCheck(
        found.low_pct <= pct <= found.high_pct,
        low <= performance_pct <= high,
        clearly_trivial_pct == found.clearly_trivial_pct,
        policy,
    )


def confidence_hold(
    payload: DocumentConfidencePayload, policy: PolicyRef, *, confidence_pct: Decimal
) -> ConfidenceDecision:
    """Below the floor a document is held for a person; auto-accept stays off while the policy
    principal is dormant (the payload cannot enable it)."""
    hold = confidence_pct < payload.hold_below_pct
    auto = (
        payload.auto_accept_enabled
        and not hold
        and confidence_pct >= payload.auto_accept_above_pct
    )
    return ConfidenceDecision(hold, auto, policy)


def required_review_levels(
    payload: ReviewLevelsPayload, policy: PolicyRef, *, tier: int
) -> RequiredLevels:
    """Q-18: the review levels a tier needs, in the payload's order."""
    row = _row_for(payload.tiers, lambda t: t.tier == tier, f"tier:{tier}")
    return RequiredLevels(row.tier, tuple(row.required_levels), row.second_partner_review, policy)


def return_approval_policy(
    payload: ReturnApprovalPolicyPayload, policy: PolicyRef, *, client_id: UUID
) -> ReturnApproval:
    """BH-TAX-02: the signing partner named for the client gives final approval; export waits
    for it. A client with no assignment has no approver yet (None), never a default."""
    assigned = next((a for a in payload.applies_to if a.client_id == client_id), None)
    return ReturnApproval(
        payload.code,
        assigned.approver_user_id if assigned is not None else None,
        payload.export_condition == "after_final_approval",
        policy,
    )


def ssars_framework_for(
    payload: SsarsCasSettingsPayload, policy: PolicyRef, *, period_end: date
) -> SsarsFramework:
    """SSARS 27 applies to periods ending on or after Dec 15, 2026, or earlier when the firm
    adopted it early: then a CAS by-product, before it AR-C 70 preparation."""
    after = payload.early_adopt_ssars27 or period_end >= SSARS27_BOUNDARY
    return SsarsFramework("cas_by_product" if after else "ar_c_70_preparation", policy)


def attribute_sample_size(
    payload: AttributeSampleSizesPayload,
    policy: PolicyRef,
    *,
    rmm: Rmm,
    tolerable_pct: Decimal,
    expected_pct: Decimal,
    confidence_pct: Decimal,
) -> AttributeSize:
    """A-03-T10 (ADR-340 §6): the table's size for the RMM and rates, at the table's confidence.
    A confidence the table is not written at, or a combination it has no row for, is a question
    the firm's standard does not answer (`standard_row_missing`); sampling never guesses one."""
    if confidence_pct != payload.confidence_pct:
        raise StandardRowMissing(facts={"missing": f"attribute_size:confidence:{confidence_pct}"})
    row = _row_for(
        payload.rows,
        lambda r: (
            r.rmm == rmm and r.tolerable_pct == tolerable_pct and r.expected_pct == expected_pct
        ),
        f"attribute_size:{rmm}:{tolerable_pct}:{expected_pct}",
    )
    return AttributeSize(row.size, payload.confidence_pct, policy)
