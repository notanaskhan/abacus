"""The audits family contract, v1: AUD-01, AUD-02 and AUD-03 (A-01-T02 stub; ADR-139, P-36).
Contract: `docs/contracts/audits-cockpit.md`; spec: SPEC-330; screens `docs/screens/AUD-01.md`
to `AUD-03.md`.

`$auditId` is the assurance work item (P-04). Behind `audits.cockpit`: off, every route here
answers 404; on, 501 `not_implemented` until the task that implements it (profile and phase
are live since A-01-T05; the index, cockpit and source documents since A-01-T08 to T10; release
and archive records A-01-T23). Firm routes resolve the work item through `engagements.api`:
outside the tenant or behind a wall it answers 404, and no response carries a count of hidden
rows (INV-3, DEC-43). No `/v1/audits` route serves a client principal (INV-4): the index refuses
portal sessions before it reads, although `engagement.read_metadata` holds client cells for
SPEC-020.

The three record writes are human only: their matrix rows deny agent and system, and the tables'
CHECKs refuse a non-human row (INV-1).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel._flags import AUDITS_COCKPIT
from abacus.kernel._statuses import (
    AuditEngagementStatus,
    AuditSectionStatus,
    EvidenceScreeningStatus,
    RequestStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.assurance import cockpit, index, phase
from abacus.modules.assurance.sections import Band, Grammar, Segment, TagClassification
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    authorise,
    current_context,
)
from abacus.modules.requests.api import (
    RequestLatestUploadOut,
    RequestOwedByOut,
    source_documents,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

# The assurance engagement types an audits row can carry (engagements' `EngagementType`, attest
# families only). Single audit is not a member (D10, DEC-19).
AuditEngagementType = Literal[
    "fs_audit",
    "ebp_audit",
    "review",
    "compilation",
    "preparation",
    "agreed_upon_procedures",
    "soc1",
    "soc2",
    "readiness",
    "internal_audit",
]
# EBP plan kinds (A-01 §4.2 M1): health and welfare plans stay off until the BAA chain exists.
EbpPlanKind = Literal["dc", "403b", "db"]
ReportDueWindow = Literal["any", "7d", "14d", "30d"]
# Report-due colour (AUD-01 spec): ≤ 7 days red-ink 500, ≤ 30 days amber-ink, later ink-2.
ReportDueTone = Literal["past_due", "within_7_days", "within_30_days", "later"]
ArchiveState = Literal["archiving", "archived"]  # C2 `audit_engagement` codes
PhaseMode = Literal["recorded", "derived"]
DockTab = Literal["agent", "viewer"]
LinkStatus = Literal["live", "planned"]
ReadOnlyReason = Literal["archived"]
ReportKind = Literal["opinion", "no_report"]
SourceSort = Literal["missing_first", "received_first"]


# --- AUD-01 index -------------------------------------------------------------------------------


class AuditRunBadgeOut(BaseModel):
    """The "Processing" pill and its popover (AUD-01 d), from a C6 v1 engagement run only; the v1
    policy ticks never produce one (DV-11). `blocked_on_role` is the decider's role code."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    run_number: Annotated[int, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    started_by_user_id: Annotated[UUID, classified("internal")]
    started_by_name: Annotated[str, classified("internal")]
    workpapers_complete: Annotated[int, classified("internal")]
    workpapers_total: Annotated[int, classified("internal")]
    blocked_on_role: Annotated[Literal["partner", "manager"] | None, classified("internal")] = None


class AuditIndexTagOut(BaseModel):
    """A tag from a registered index-tag provider (DV-10): code-built text, never model text."""

    model_config = ConfigDict(frozen=True)

    source: Annotated[str, classified("internal")]
    code: Annotated[str, classified("internal")]
    text: Annotated[str, classified("confidential")]
    classification: Annotated[TagClassification, classified("internal")]


class AuditPbcOut(BaseModel):
    """ "11 of 24": received over the client-visible requests of the work item's published PBC
    binders. The row's `pbc` is null before G3 (no published PBC binder, DEC-39)."""

    model_config = ConfigDict(frozen=True)

    received: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]


class AuditArchiveOut(BaseModel):
    """The Archive cell: "Archive in 13 days" (clock from the release date + 60, on `kernel.clock`)
    or "Archived" with the firm-tool reference of an external archive (DV-4)."""

    model_config = ConfigDict(frozen=True)

    state: Annotated[ArchiveState, classified("internal")]  # C2 `audit_engagement`
    days_left: Annotated[int | None, classified("internal")] = None
    firm_tool_ref: Annotated[str | None, classified("confidential")] = None


class AuditIndexRowOut(BaseModel):
    """An AUD-01 row: metadata only, after `visible()` (INV-3). No amount, materiality or
    severity (AUD-01 AVOID)."""

    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    name: Annotated[str, classified("confidential")]
    engagement_type: Annotated[AuditEngagementType, classified("internal")]
    segment: Annotated[Segment, classified("internal")]
    ebp_plan_kind: Annotated[EbpPlanKind | None, classified("internal")] = None
    limited_scope_103a3c: Annotated[bool, classified("internal")] = False
    is_group_audit: Annotated[bool, classified("internal")] = False
    period_label: Annotated[str | None, classified("confidential")] = None
    phase: Annotated[AuditEngagementStatus, classified("internal")]  # C2
    released_on: Annotated[date | None, classified("internal")] = None
    run_badge: Annotated[AuditRunBadgeOut | None, classified("internal")] = None
    tags: Annotated[list[AuditIndexTagOut], classified("confidential")] = []
    pbc: Annotated[AuditPbcOut | None, classified("internal")] = None
    partner_initials: Annotated[str | None, classified("internal")] = None
    manager_initials: Annotated[str | None, classified("internal")] = None
    office_id: Annotated[UUID | None, classified("internal")] = None
    office_name: Annotated[str | None, classified("internal")] = None
    report_due_on: Annotated[date | None, classified("internal")] = None
    report_due_tone: Annotated[ReportDueTone | None, classified("internal")] = None
    archive: Annotated[AuditArchiveOut | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class AuditIndexSummaryOut(BaseModel):
    """The caption ("27 engagements · EBP 14 · FS audit 6 · Review 4 · Compilation/preparation
    3"), over the same `visible()` predicate as the rows."""

    model_config = ConfigDict(frozen=True)

    ebp: Annotated[int, classified("internal")]
    fs_audit: Annotated[int, classified("internal")]
    review: Annotated[int, classified("internal")]
    compilation_preparation: Annotated[int, classified("internal")]
    soc: Annotated[int, classified("internal")] = 0
    internal_audit: Annotated[int, classified("internal")] = 0


class AuditIndexPage(ListPage[AuditIndexRowOut]):
    """The P-36 envelope: `counts` per `audit_engagement` phase code **minus the active tile**
    (the tiles keep their own counts when one is pressed); `facets.segment` the segments with
    their counts (only registered segments the firm is entitled to); `facets.type`, `partner`,
    `office`, `period`. The tiles sum to `total`. No hidden-by-wall field."""

    summary: Annotated[AuditIndexSummaryOut, classified("internal")]


# --- AUD-02 cockpit -----------------------------------------------------------------------------


class AuditBarOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: Annotated[str, classified("confidential")]
    methodology_label: Annotated[str | None, classified("internal")] = None
    # "Started 9:24 AM": a C6 engagement run only (DV-11).
    run_started_at: Annotated[datetime | None, classified("internal")] = None
    # The Auto mode toggle: null while the firm has no `engagement_run.auto_mode` (P-10-T39).
    auto_mode: Annotated[bool | None, classified("internal")] = None


class AuditOverviewOut(BaseModel):
    """The rail's OverviewCard."""

    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    name: Annotated[str, classified("confidential")]
    period_label: Annotated[str | None, classified("confidential")] = None
    # "Processing" (derived, never stored) is drawn from `audit_bar.run_started_at` (DV-11).
    phase: Annotated[AuditEngagementStatus, classified("internal")]


class AuditSectionRowOut(BaseModel):
    """A rail row from a registered section provider (DV-1): a missing provider hides the row.
    `sub_line` is code-built ("11 of 24 received", "Complete · 9:26 AM"), never model text."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]
    work_item_ref: Annotated[UUID, classified("internal")]
    # C2 `audit_section`; null on an Overview link row ("Client"), which has no state.
    section_state: Annotated[AuditSectionStatus | None, classified("internal")] = None
    grammar: Annotated[Grammar, classified("internal")]
    sub_line: Annotated[str | None, classified("confidential")] = None
    route: Annotated[str, classified("internal")]  # manifest screen ID
    link: Annotated[LinkStatus, classified("internal")]  # planned: text without a chevron (DV-1)
    blocked_on_user_id: Annotated[UUID | None, classified("internal")] = None
    blocked_on_name: Annotated[str | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class AuditBandOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[Band, classified("internal")]
    collapsed: Annotated[bool, classified("internal")] = False
    rows: Annotated[list[AuditSectionRowOut], classified("confidential")] = []


class AuditCockpitOut(BaseModel):
    """AUD-02's host: audit bar, overview card, bands of registered rows and the dock tabs.
    `allowed_actions` from `assurance.record_phase`, `engagement.update`, `export.create`,
    `agent.pause`; empty for metadata-only roles and archived work items."""

    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    audit_bar: Annotated[AuditBarOut, classified("confidential")]
    overview: Annotated[AuditOverviewOut, classified("confidential")]
    bands: Annotated[list[AuditBandOut], classified("confidential")] = []
    dock_tabs: Annotated[list[DockTab], classified("internal")] = []
    phase_mode: Annotated[PhaseMode, classified("internal")] = "recorded"
    read_only_reason: Annotated[ReadOnlyReason | None, classified("internal")] = None
    version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []


# --- EBP profile and record-mode writes ---------------------------------------------------------


class AuditProfileIn(BaseModel):
    """The EBP label facts ("EBP DC · §103(a)(3)(C)"); a field left out is unchanged."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ebp_plan_kind: Annotated[EbpPlanKind | None, classified("internal")] = None
    limited_scope_103a3c: Annotated[bool | None, classified("internal")] = None
    standards_set_id: Annotated[UUID | None, classified("internal")] = None
    seen_version: Annotated[int, classified("internal")]

    @model_validator(mode="after")
    def _a_change(self) -> AuditProfileIn:
        """422: the label is a yes or no (never null), and a PATCH changes at least one fact."""
        if "limited_scope_103a3c" in self.model_fields_set and self.limited_scope_103a3c is None:
            raise ValueError("limited_scope_103a3c is true or false")
        if not self.model_fields_set - {"seen_version"}:
            raise ValueError("nothing to change")
        return self


class AuditProfileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    ebp_plan_kind: Annotated[EbpPlanKind | None, classified("internal")] = None
    limited_scope_103a3c: Annotated[bool, classified("internal")]
    standards_set_id: Annotated[UUID | None, classified("internal")] = None
    version: Annotated[int, classified("internal")]


class AuditPhaseIn(BaseModel):
    """A record-mode forward move by a named person (409 `phase_backward`, `phase_skip`,
    `phase_follows_gate`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    to: Annotated[AuditEngagementStatus, classified("internal")]
    reason: Annotated[SingleLineText | None, Field(max_length=300), classified("confidential")] = (
        None
    )


class AuditPhaseOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    event_id: Annotated[UUID, classified("internal")]
    from_phase: Annotated[AuditEngagementStatus, classified("internal")]
    to_phase: Annotated[AuditEngagementStatus, classified("internal")]
    mode: Annotated[PhaseMode, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]
    version: Annotated[int, classified("internal")]


class ReleaseRecordIn(BaseModel):
    """ "Report released outside Accrued on Jul 29, 2026" (interim G8); a future date answers 422
    `release_date_future`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_released_on: Annotated[date, classified("internal")]
    report_kind: Annotated[ReportKind, classified("internal")]


class ReleaseRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    report_released_on: Annotated[date, classified("internal")]
    report_kind: Annotated[ReportKind, classified("internal")]
    phase: Annotated[AuditEngagementStatus, classified("internal")]
    archive_due_on: Annotated[date, classified("internal")]  # released + 60 days
    recorded_at: Annotated[datetime, classified("internal")]


class ArchiveRecordIn(BaseModel):
    """The external archive against a ready final binder export (interim G9): 409
    `final_export_required` or `export_stale` otherwise."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    export_id: Annotated[UUID, classified("internal")]
    firm_tool_ref: Annotated[
        SingleLineText, Field(min_length=1, max_length=120), classified("confidential")
    ]


class ArchiveRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    export_id: Annotated[UUID, classified("internal")]
    manifest_sha256: Annotated[str, classified("internal")]
    phase: Annotated[AuditEngagementStatus, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]


# --- AUD-02 canvas and AUD-03 -------------------------------------------------------------------


class SourceDocumentRowOut(BaseModel):
    """A request row across the work item's PBC binders, with the C5 v1.1 additive fields
    (A-01-T10). Requested rows carry no upload, glyph or Linked count."""

    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[RequestStatus, classified("internal")]  # C2 (DEC-09)
    overdue: Annotated[bool, classified("internal")]  # derived from due_on < clock.today()
    requested_at: Annotated[datetime | None, classified("internal")] = None
    due_on: Annotated[date | None, classified("internal")] = None
    owed_by: Annotated[RequestOwedByOut | None, classified("internal")] = (
        None  # its `display` is C
    )
    latest_upload: Annotated[RequestLatestUploadOut | None, classified("internal")] = (
        None  # `path_label` C
    )
    match_confidence: Annotated[int | None, Field(ge=0, le=100), classified("internal")] = None
    linked_count: Annotated[int | None, classified("internal")] = None
    screening: Annotated[EvidenceScreeningStatus | None, classified("internal")] = None
    returned_reason: Annotated[str | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class SourceDocumentGroupOut(BaseModel):
    """A category band ("Plan documents · 3 of 5"). `counted` is false for a band outside the
    totals ("Sample-driven · 0", populated by A-03)."""

    model_config = ConfigDict(frozen=True)

    category_id: Annotated[UUID | None, classified("internal")] = None
    label: Annotated[str, classified("confidential")]
    received: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    counted: Annotated[bool, classified("internal")] = True
    rows: Annotated[list[SourceDocumentRowOut], classified("confidential")] = []


class SourceDocumentsOut(BaseModel):
    """24 requests = 11 received + 1 needs review + 12 requested at E0; the groups foot to the
    totals and the rail's "11 of 24 received" reads the same numbers."""

    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    received: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    needs_review: Annotated[int, classified("internal")]
    requested: Annotated[int, classified("internal")]
    groups: Annotated[list[SourceDocumentGroupOut], classified("confidential")] = []


# --- routes -------------------------------------------------------------------------------------


async def _flag_on(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, AUDITS_COCKPIT):
        raise NotFound(AUDITS_COCKPIT.name)


async def _authorise_on_item(ctx: AuthContext, action: str, work_item_id: UUID) -> None:
    """The route's one action on the work item's engagement: 404 outside the tenant, for another
    kind of work item or behind a wall; 403 by role."""
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    await authorise(ctx, action, ref.resource())


async def _allowed(ctx: AuthContext, action: str, work_item_id: UUID | None) -> None:
    """Security review (DEC-261): every route authorises before the flag or the stub answers, so
    no principal learns the flag state it may not use. No `/v1/audits` route serves a client
    principal (INV-4), an agent or the system (the stubs and record mode are a person's)."""
    if ctx.client or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")
    if work_item_id is not None:
        await _authorise_on_item(ctx, action, work_item_id)


async def _stub(ctx: AuthContext, action: str, work_item_id: UUID | None = None) -> NoReturn:
    await _allowed(ctx, action, work_item_id)
    await _flag_on(ctx)
    raise NotImplementedYet


audits_router = AbacusRouter(prefix="/v1/audits", tags=["audits"])


@audits_router.get(
    "", action="engagement.read_metadata", response_model=AuditIndexPage, errors=(501,)
)
async def audits_index_route(
    ctx: Ctx,
    segment: Annotated[Segment | None, Query()] = None,
    type_: Annotated[AuditEngagementType | None, Query(alias="type")] = None,
    phase: Annotated[AuditEngagementStatus | None, Query()] = None,
    partner: Annotated[UUID | None, Query()] = None,
    office: Annotated[UUID | None, Query()] = None,
    due: Annotated[ReportDueWindow, Query()] = "any",
    period: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditIndexPage:
    """AUD-01: rows grouped by phase in tile order, then by report due (A-01-T08, DEC-311)."""
    await _allowed(ctx, "engagement.read_metadata", None)
    await _flag_on(ctx)
    filters = index.IndexFilters(
        segment=segment,
        type=type_,
        phase=phase.value if phase is not None else None,
        partner=partner,
        office=office,
        due=due,
        period=period,
        q=q,
    )
    page, summary = await index.audits_index(ctx, filters, cursor=cursor, limit=limit)
    return AuditIndexPage(
        items=[AuditIndexRowOut.model_validate(r, from_attributes=True) for r in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
        total_capped=page.total_capped,
        counts=page.counts,
        facets=page.facets,
        summary=AuditIndexSummaryOut.model_validate(summary, from_attributes=True),
    )


@audits_router.get(
    "/{work_item_id}/cockpit",
    action="engagement.read_metadata",
    response_model=AuditCockpitOut,
    errors=(501,),
)
async def audit_cockpit_route(work_item_id: UUID, ctx: Ctx) -> AuditCockpitOut:
    """AUD-02's host projection (A-01-T09, DEC-312): the bar and overview are metadata; the
    bands, dock and actions also need `engagement.read`."""
    await _allowed(ctx, "engagement.read_metadata", work_item_id)
    await _flag_on(ctx)
    view = await cockpit.audit_cockpit(ctx, work_item_id)
    return AuditCockpitOut.model_validate(view, from_attributes=True)


@audits_router.patch(
    "/{work_item_id}/profile",
    action="engagement.update",
    response_model=AuditProfileOut,
    errors=(409, 501),
)
async def audit_profile_route(
    work_item_id: UUID, body: AuditProfileIn, ctx: Ctx
) -> AuditProfileOut:
    """The EBP label facts (A-01-T05); 409 `stale_version`."""
    await _allowed(ctx, "engagement.update", work_item_id)
    await _flag_on(ctx)
    changes = body.model_dump(exclude_unset=True, exclude={"seen_version"})
    made = await phase.update_profile(ctx, work_item_id, body.seen_version, changes)
    return AuditProfileOut(
        work_item_id=made.work_item_id,
        ebp_plan_kind=cast(EbpPlanKind | None, made.ebp_plan_kind),
        limited_scope_103a3c=made.limited_scope_103a3c,
        standards_set_id=made.standards_set_id,
        version=made.version,
    )


@audits_router.post(
    "/{work_item_id}/phase",
    action="assurance.record_phase",
    response_model=AuditPhaseOut,
    status_code=201,
    errors=(409, 501),
)
async def audit_phase_route(
    work_item_id: UUID, body: AuditPhaseIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AuditPhaseOut:
    """Record mode (A-01-T05): a named person moves the phase forward one step."""
    await _allowed(ctx, "assurance.record_phase", work_item_id)
    await _flag_on(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        made = await phase.record_phase(ctx, work_item_id, body.to.value, body.reason)
        out = AuditPhaseOut(
            work_item_id=made.work_item_id,
            event_id=made.event_id,
            from_phase=AuditEngagementStatus(made.from_phase),
            to_phase=AuditEngagementStatus(made.to_phase),
            mode=cast(PhaseMode, made.mode),
            recorded_at=made.recorded_at,
            version=made.version,
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="audits.record_phase",
        key=idempotency_key,
        body={"work_item_id": str(work_item_id), **body.model_dump(mode="json")},
        run=run,
    )
    return AuditPhaseOut.model_validate(stored.body)


@audits_router.post(
    "/{work_item_id}/release-record",
    action="assurance.record_release",
    response_model=ReleaseRecordOut,
    status_code=201,
    errors=(409, 501),
)
async def audit_release_record_route(
    work_item_id: UUID, body: ReleaseRecordIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRecordOut:
    """Interim G8, the engagement partner with fresh MFA (A-01-T23)."""
    await _stub(ctx, "assurance.record_release", work_item_id)


@audits_router.post(
    "/{work_item_id}/archive-record",
    action="assurance.record_archive",
    response_model=ArchiveRecordOut,
    status_code=201,
    errors=(409, 501),
)
async def audit_archive_record_route(
    work_item_id: UUID, body: ArchiveRecordIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ArchiveRecordOut:
    """Interim G9 against a ready final binder export, with fresh MFA (A-01-T23)."""
    await _stub(ctx, "assurance.record_archive", work_item_id)


@audits_router.get(
    "/{work_item_id}/source-documents",
    action="request_item.read",
    response_model=SourceDocumentsOut,
    errors=(501,),
)
async def audit_source_documents_route(
    work_item_id: UUID,
    ctx: Ctx,
    binder: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[SourceSort, Query()] = "missing_first",
) -> SourceDocumentsOut:
    """AUD-02's canvas and AUD-03 (A-01-T10, DEC-313): the work item's asked PBC requests by
    category, with the C5 v1.1 row facts (firm only: client principals were refused)."""
    await _allowed(ctx, "request_item.read", work_item_id)
    await _flag_on(ctx)
    found = await source_documents(ctx, work_item_id, binder_id=binder, q=q, sort=sort)
    return SourceDocumentsOut.model_validate(found, from_attributes=True)
