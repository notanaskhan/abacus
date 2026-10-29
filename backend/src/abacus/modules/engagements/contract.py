"""The engagements family contract, v2: ENG-01, ENG-02 and ENG-03 (P-07-T05 stub; ADR-139,
P-36). An additive C1 v1.1 note. Contract: `docs/contracts/engagements-v2.md`; spec: SPEC-321.

Live for every firm since P-07-T59 retired `engagements.v2` (DEC-905): P-07-T15 the index,
record, gates and recorded letter; P-07-T16 the type catalogue, drafts and create. No seed slice
yet (P-07-T11), so no fixtures.

The live routes stay where they are and keep their shapes: `GET /v1/engagements` (a plain list),
`GET /v1/engagements/{id}` (C1's `EngagementOut`), `PUT …/letter` (SPEC-025) and `POST
/v1/engagements`. The v2 index and record are served beside them, at `/v1/engagements/index` and
`/v1/engagements/{id}/record`, and take over the plain paths when P-07-T15 retires the v1 consumer
(contract change log). `/index` is matched before the live `/{engagement_id}` only because
`api.ROUTERS` lists this module's routers first (a test holds that order).

Single audit is out of scope (D10, DEC-19): no catalogue code, enum member or seed row exists for
it, and a draft or create naming it answers 422 `unknown_engagement_type` like any unknown code.
The ENG-03 "Coming soon" tile is static frontend copy.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import EngagementStatus, LetterRecordStatus
from abacus.kernel.classification import classified
from abacus.kernel.listing import ListPage
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements import drafts as draft_model
from abacus.modules.engagements import index as index_model
from abacus.modules.engagements import record as record_model
from abacus.modules.engagements import transitions
from abacus.modules.engagements.service import EngagementType
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

ServiceLine = Literal["audit", "tax", "cas", "advisory"]
WorkItemKind = Literal["assurance", "tax_return", "close", "notice", "advisory_project"]
Gate = Literal["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]
# `engagement_contacts.designation` (migration 0082, DEC-63).
Designation = Literal[
    "approver_of_record",
    "ske_designee",
    "signing_officer",
    "plan_administrator",
    "tcwg_member",
    "primary_contact",
]
NextDueWindow = Literal["past_due", "within_7_days", "within_30_days"]
PeriodFilter = Literal["current", "prior", "all"]
DueTone = Literal["past_due", "soon", "normal"]
LetterEvent = Literal["sent", "viewed"]
RailBand = Literal["details", "review_delivery", "client_portal"]
ReadOnlyReason = Literal["archived"]
# The ENG-03 catalogue: Tax 8, Audit & assurance 8, CAS & Advisory 2 (P-07 §3.6 Story 6.3). A code
# catalogue (P-07-T16), never firm content; `single_audit` is not a member and never will be (D10).
CatalogueTypeCode = Literal[
    "form_1040",
    "form_1041",
    "form_1065",
    "form_1120s",
    "form_1120",
    "form_990",
    "forms_706_709",
    "notice_response",
    "ebp_audit",
    "fs_audit",
    "review",
    "compilation",
    "preparation",
    "agreed_upon_procedures",
    "soc1",
    "soc2",
    "cas_monthly_close",
    "advisory",
]
CatalogueFamily = Literal["tax", "audit_assurance", "cas_advisory"]
Entitlement = Literal["attest", "group_audit"]
Availability = Literal["available", "needs_entitlement"]
WizardStep = Literal[
    "client_type",
    "standards_methodology",
    "period_deadlines",
    "team_independence",
    "binder_portal",
    "letter_review",
]
LetterMode = Literal["signed", "not_required_this_year"]
# A draft's type: a catalogue code the server checks (422 `unknown_engagement_type`), so a stale
# or excluded code is a domain answer, not a schema error.
TypeCodeIn = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,40}$")]


# --- Shared parts -------------------------------------------------------------------------------


class GateBlockerRefOut(BaseModel):
    """What blocks a gate: an opaque reference and a registered reason code, never prose."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    reason_code: Annotated[str, classified("internal")]


class EngagementGateOut(BaseModel):
    """One gate from its registered provider (G1, G2 and the interim G3 in P-07; G4 to G9 when
    A-04, A-06 and A-07 register). Met, blocked (blockers) or not started (neither)."""

    model_config = ConfigDict(frozen=True)

    gate: Annotated[Gate, classified("internal")]
    met: Annotated[bool, classified("internal")]
    blockers: Annotated[list[GateBlockerRefOut], classified("internal")] = []
    met_at: Annotated[datetime | None, classified("internal")] = None
    met_by_user_id: Annotated[UUID | None, classified("internal")] = None  # G1: the decider


class EngagementLetterSummaryOut(BaseModel):
    """ENG-01's Letter column and ENG-02's summary: "✓ Signed {date}", "Sent {date} · 1 of 2"."""

    model_config = ConfigDict(frozen=True)

    status: Annotated[LetterRecordStatus, classified("internal")]  # C2 `letter_record`
    signed_on: Annotated[date | None, classified("internal")] = None
    last_event: Annotated[LetterEvent | None, classified("internal")] = None
    last_event_on: Annotated[date | None, classified("internal")] = None
    signed_count: Annotated[int, classified("internal")] = 0
    signer_count: Annotated[int, classified("internal")] = 0
    not_required_this_year: Annotated[bool, classified("internal")] = False


class EngagementWorkItemLineOut(BaseModel):
    """A work-item sub-line from its kind's provider, in the kind's own status words."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[WorkItemKind, classified("internal")]
    label: Annotated[str, classified("confidential")]
    pill_object: Annotated[str | None, classified("internal")] = None
    pill_code: Annotated[str | None, classified("internal")] = None


class EngagementNextDueOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    on: Annotated[date, classified("internal")]
    tone: Annotated[DueTone, classified("internal")]
    # The deadline's own sub-line ("§754 election deadline", "Report target"): seed data.
    label: Annotated[str | None, classified("confidential")] = None


# --- ENG-01 index -------------------------------------------------------------------------------


class EngagementIndexRowOut(BaseModel):
    """An ENG-01 row: metadata only, after `visible()` (INV-3)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    client_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    client_entity_id: Annotated[UUID, classified("internal")]
    type: Annotated[EngagementType, classified("internal")]
    service_line: Annotated[ServiceLine, classified("internal")]
    status: Annotated[EngagementStatus, classified("internal")]  # C2
    period_label: Annotated[str | None, classified("confidential")] = None
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    office_id: Annotated[UUID | None, classified("internal")] = None
    office_name: Annotated[str | None, classified("internal")] = None
    partner_user_id: Annotated[UUID | None, classified("internal")] = None
    partner_initials: Annotated[str | None, classified("internal")] = None
    work_items: Annotated[list[EngagementWorkItemLineOut], classified("confidential")] = []
    letter: Annotated[EngagementLetterSummaryOut, classified("internal")]
    next_due: Annotated[EngagementNextDueOut | None, classified("confidential")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class EngagementIndexSummaryOut(BaseModel):
    """The ENG-01 summary line, over the same `visible()` predicate as the rows."""

    model_config = ConfigDict(frozen=True)

    prospect: Annotated[int, classified("internal")]
    awaiting_letter: Annotated[int, classified("internal")]  # Accepted without a recorded letter
    past_due: Annotated[int, classified("internal")]


class EngagementIndexPage(ListPage[EngagementIndexRowOut]):
    """The P-36 envelope: `counts` per engagement status minus the selected tile (the seven tiles;
    `declined` never shows), `facets.service_line` the segments; both from one grouped query. The
    tiles sum to `total`."""

    summary: Annotated[EngagementIndexSummaryOut, classified("internal")]


# --- ENG-02 record ------------------------------------------------------------------------------


class EngagementRailRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]  # the band's row code
    text: Annotated[str | None, classified("confidential")] = None
    user_id: Annotated[UUID | None, classified("internal")] = None
    on: Annotated[date | None, classified("internal")] = None
    pill_object: Annotated[str | None, classified("internal")] = None
    pill_code: Annotated[str | None, classified("internal")] = None


class EngagementRailBandOut(BaseModel):
    """A rail band. Content bands need `engagement.read`; a metadata-only role gets the others."""

    model_config = ConfigDict(frozen=True)

    band: Annotated[RailBand, classified("internal")]
    rows: Annotated[list[EngagementRailRowOut], classified("confidential")]


class EngagementDesignationOut(BaseModel):
    """ENG-02's contacts block: approver of record, SKE designee (DEC-63)."""

    model_config = ConfigDict(frozen=True)

    designation: Annotated[Designation, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]


class EngagementTabCountsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_items: Annotated[int, classified("internal")]
    team: Annotated[int, classified("internal")]


# `transitions.HOLD_REASONS`, as the API's enum (a test holds the two equal).
HoldReason = Literal[
    "client_unresponsive", "fees_outstanding", "scope_change", "independence_review", "other"
]


class EngagementRecordOut(BaseModel):
    """The extended C1 projection (C1 v1.1): subbar facts, rail bands, contacts, letter summary,
    gates, tab counts and why it is read-only."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    client_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    client_entity_id: Annotated[UUID, classified("internal")]
    client_entity_name: Annotated[str, classified("confidential")]
    type: Annotated[EngagementType, classified("internal")]
    service_line: Annotated[ServiceLine, classified("internal")]
    status: Annotated[EngagementStatus, classified("internal")]  # C2
    period_label: Annotated[str | None, classified("confidential")] = None
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    bands: Annotated[list[EngagementRailBandOut], classified("confidential")]
    contacts: Annotated[list[EngagementDesignationOut], classified("confidential")] = []
    letter: Annotated[EngagementLetterSummaryOut, classified("internal")]
    gates: Annotated[list[EngagementGateOut], classified("internal")]
    tab_counts: Annotated[EngagementTabCountsOut, classified("internal")]
    read_only_reason: Annotated[ReadOnlyReason | None, classified("internal")] = None
    # ENG-02's status pill while On hold names the reason code (DEC-344); null otherwise.
    hold_reason: Annotated[HoldReason | None, classified("internal")] = None
    version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []


# --- The interim recorded letter (G3 until C7) --------------------------------------------------


class LetterRecordIn(BaseModel):
    """ "Record signed letter…": both parties' dates on or after the G1 decision (409
    `letter_before_acceptance`); or the EP's "Not required this year" with a reason, only while
    the firm setting `allow_letter_exceptions` is on."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    mode: Annotated[LetterMode, classified("internal")]
    client_signed_on: Annotated[date | None, classified("internal")] = None
    firm_signed_on: Annotated[date | None, classified("internal")] = None
    client_signer_contact_id: Annotated[UUID | None, classified("internal")] = None
    firm_signer_user_id: Annotated[UUID | None, classified("internal")] = None
    # The signed copy, stored write-once through `evidence` first (P-07 Story 6.2).
    signed_copy_version_id: Annotated[UUID | None, classified("internal")] = None
    not_required_reason: Annotated[
        MultiLineText | None,
        Field(default=None, min_length=1, max_length=1000),
        classified("confidential"),
    ]


class EngagementLetterRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    status: Annotated[LetterRecordStatus, classified("internal")]  # C2 `letter_record`
    mode: Annotated[LetterMode, classified("internal")]
    client_signed_on: Annotated[date | None, classified("internal")] = None
    firm_signed_on: Annotated[date | None, classified("internal")] = None
    client_signer_contact_id: Annotated[UUID | None, classified("internal")] = None
    firm_signer_user_id: Annotated[UUID | None, classified("internal")] = None
    signed_copy_version_id: Annotated[UUID | None, classified("internal")] = None
    acceptance_decided_at: Annotated[datetime, classified("internal")]  # the G1 decision
    recorded_by: Annotated[UUID, classified("internal")]  # always a person (INV-5)
    recorded_at: Annotated[datetime, classified("internal")]
    engagement_status: Annotated[EngagementStatus, classified("internal")]  # `contracted` once met


# --- ENG-03: the type catalogue -----------------------------------------------------------------


class EngagementTypeStepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: Annotated[WizardStep, classified("internal")]
    field_codes: Annotated[list[str], classified("internal")]  # the step's fields


class EngagementTypeEntryOut(BaseModel):
    """One TypeCard. Labels are the copy registry's (OQ-15), held with the code catalogue."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[CatalogueTypeCode, classified("internal")]
    engagement_type: Annotated[EngagementType, classified("internal")]
    family: Annotated[CatalogueFamily, classified("internal")]
    work_item_kind: Annotated[WorkItemKind, classified("internal")]
    label: Annotated[str, classified("public")]  # "Form 1040"
    standard_line: Annotated[str, classified("public")]  # "Individual", "AU-C 703 · ERISA"
    availability: Annotated[Availability, classified("internal")]
    entitlement: Annotated[Entitlement | None, classified("internal")] = None
    group_audit_allowed: Annotated[bool, classified("internal")] = False
    steps: Annotated[list[EngagementTypeStepOut], classified("internal")]


class EngagementTypeCatalogueOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[EngagementTypeEntryOut], classified("internal")]


# --- ENG-03: drafts and create ------------------------------------------------------------------


class DraftDeadlineIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,40}$"), classified("internal")]
    on: Annotated[date, classified("internal")]


class DraftTeamMemberIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    role: Annotated[str, Field(pattern=r"^[a-z_]{1,40}$"), classified("internal")]


class EngagementDraftPayload(BaseModel):
    """Identifiers and typed values only: no TIN and no free text beyond the engagement name
    (P-07 §4.2 M2). Absent fields are not chosen yet."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Annotated[
        SingleLineText | None,
        Field(default=None, min_length=1, max_length=200),
        classified("confidential"),
    ]
    methodology_version_id: Annotated[UUID | None, classified("internal")] = None
    standards_code: Annotated[
        str | None, Field(default=None, max_length=60), classified("internal")
    ]
    scope_code: Annotated[str | None, Field(default=None, max_length=60), classified("internal")]
    fiscal_period_start: Annotated[date | None, classified("confidential")] = None
    fiscal_period_end: Annotated[date | None, classified("confidential")] = None
    period_label: Annotated[
        str | None, Field(default=None, max_length=40), classified("confidential")
    ]
    deadlines: Annotated[list[DraftDeadlineIn], Field(max_length=20), classified("internal")] = []
    team: Annotated[list[DraftTeamMemberIn], Field(max_length=50), classified("internal")] = []
    eqr_user_id: Annotated[UUID | None, classified("internal")] = None
    group_audit: Annotated[bool, classified("internal")] = False
    portal_contact_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")] = []
    prior_engagement_id: Annotated[UUID | None, classified("internal")] = None


class EngagementDraftIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: Annotated[UUID | None, classified("internal")] = None
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    type_code: Annotated[TypeCodeIn | None, classified("internal")] = None
    step: Annotated[WizardStep, classified("internal")] = "client_type"
    # Absent: nothing chosen yet beyond the client and type.
    payload: Annotated[EngagementDraftPayload | None, classified("confidential")] = None


class EngagementDraftPatchIn(BaseModel):
    """Autosave: absent fields are unchanged; `seen_version` behind answers 409 `stale_version`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=0), classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")] = None
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    type_code: Annotated[TypeCodeIn | None, classified("internal")] = None
    step: Annotated[WizardStep | None, classified("internal")] = None
    payload: Annotated[EngagementDraftPayload | None, classified("confidential")] = None


class EngagementDraftOut(BaseModel):
    """A draft, its owner's only (scope own, OQ-17); "Draft · saved 9:39 AM" is `saved_at`."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    created_by: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")] = None
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    type_code: Annotated[CatalogueTypeCode | None, classified("internal")] = None
    step: Annotated[WizardStep, classified("internal")]
    payload: Annotated[EngagementDraftPayload, classified("confidential")]
    prospect_engagement_id: Annotated[UUID | None, classified("internal")] = None
    gates: Annotated[list[EngagementGateOut], classified("internal")] = []
    version: Annotated[int, classified("internal")]
    saved_at: Annotated[datetime, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []


class DraftValidateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step: Annotated[WizardStep, classified("internal")]


class DraftProblemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: Annotated[str, classified("internal")]  # a payload field code
    code: Annotated[str, classified("internal")]  # a registered problem code


class EngagementDraftValidationOut(BaseModel):
    """Per-step validation; G1 unmet on step 1 disables Next (ENG-03 d)."""

    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    step: Annotated[WizardStep, classified("internal")]
    valid: Annotated[bool, classified("internal")]
    problems: Annotated[list[DraftProblemOut], classified("internal")] = []
    gates: Annotated[list[EngagementGateOut], classified("internal")] = []


class EngagementDraftDiscardedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    discarded_at: Annotated[datetime, classified("internal")]


class AcceptanceStartedOut(BaseModel):
    """ "Start acceptance": the draft is saved, a Prospect engagement and an acceptance record
    exist, and CLI-07 opens on the record."""

    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    acceptance_record_id: Annotated[UUID, classified("internal")]
    engagement_status: Annotated[EngagementStatus, classified("internal")]  # `prospect`


class DraftCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    confirm_duplicate: Annotated[bool, classified("internal")] = False


class EngagementFromDraftOut(BaseModel):
    """One unit of work: the engagement (Accepted), its work items by type cardinality, the team
    and independence requests, the methodology pin and `engagement.created`."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    engagement_status: Annotated[EngagementStatus, classified("internal")]  # `accepted`
    work_item_ids: Annotated[list[UUID], classified("internal")]
    independence_requested_user_ids: Annotated[list[UUID], classified("internal")] = []
    methodology_version_id: Annotated[UUID | None, classified("internal")] = None


async def _intake_gate(ctx: AuthContext) -> None:
    """DEC-326's order for the acceptance half: authorise `client.intake` (its flag retired with
    P-07-T59, DEC-905)."""
    await authorise(ctx, "client.intake", Resource.firm(ctx.tenant_id))


def _letter_out(s: index_model.LetterSummary) -> EngagementLetterSummaryOut:
    return EngagementLetterSummaryOut(
        status=LetterRecordStatus(s.status),
        signed_on=s.signed_on,
        signed_count=s.signed_count,
        signer_count=s.signer_count,
        not_required_this_year=s.not_required_this_year,
    )


def _gates_out(views: list[record_model.GateView]) -> list[EngagementGateOut]:
    return [
        EngagementGateOut(
            gate=cast(Gate, v.gate),
            met=v.met,
            blockers=[
                GateBlockerRefOut(type=b.type, id=b.id, reason_code=b.reason_code)
                for b in v.blockers
            ],
            met_at=v.met_at,
            met_by_user_id=v.met_by_user_id,
        )
        for v in views
    ]


def _index_row(r: index_model.IndexRow) -> EngagementIndexRowOut:
    e = r.engagement
    return EngagementIndexRowOut(
        id=e.id,
        name=e.name,
        client_id=e.client_id,
        client_name=r.client_name,
        client_entity_id=e.client_entity_id,
        type=cast(EngagementType, e.type),
        service_line=cast(ServiceLine, e.service_line),
        status=EngagementStatus(e.status),
        period_label=e.period_label,
        fiscal_period_start=e.fiscal_period_start,
        fiscal_period_end=e.fiscal_period_end,
        office_id=e.office_id,
        office_name=r.office_name,
        partner_user_id=r.partner_user_id,
        partner_initials=r.partner_initials,
        work_items=[
            EngagementWorkItemLineOut(
                id=w.id,
                kind=cast(WorkItemKind, w.kind),
                label=w.label,
                pill_object=w.pill_object,
                pill_code=w.pill_code,
            )
            for w in r.work_items
        ],
        letter=_letter_out(r.letter),
        next_due=(
            None
            if r.next_due is None
            else EngagementNextDueOut(on=r.next_due.on, tone=r.next_due.tone)
        ),
    )


def _record_out(v: record_model.RecordView) -> EngagementRecordOut:
    e = v.engagement
    return EngagementRecordOut(
        id=e.id,
        name=e.name,
        client_id=e.client_id,
        client_name=v.client_name,
        client_entity_id=e.client_entity_id,
        client_entity_name=v.client_entity_name,
        type=cast(EngagementType, e.type),
        service_line=cast(ServiceLine, e.service_line),
        status=EngagementStatus(e.status),
        period_label=e.period_label,
        fiscal_period_start=e.fiscal_period_start,
        fiscal_period_end=e.fiscal_period_end,
        bands=[
            EngagementRailBandOut(
                band=b.band,
                rows=[
                    EngagementRailRowOut(
                        key=r.key,
                        text=r.text,
                        user_id=r.user_id,
                        on=r.on,
                        pill_object=r.pill_object,
                        pill_code=r.pill_code,
                    )
                    for r in b.rows
                ],
            )
            for b in v.bands
        ],
        contacts=[
            EngagementDesignationOut(
                designation=cast(Designation, d.designation), contact_id=d.contact_id, name=d.name
            )
            for d in v.contacts
        ],
        letter=_letter_out(v.letter),
        gates=_gates_out(v.gates),
        tab_counts=EngagementTabCountsOut(work_items=v.work_item_count, team=v.team_count),
        read_only_reason=v.read_only_reason,
        hold_reason=cast(HoldReason, e.hold_reason) if e.status == "on_hold" else None,
        version=e.version,
        allowed_actions=v.allowed_actions,
    )


def _payload_out(raw: dict[str, object]) -> EngagementDraftPayload:
    return EngagementDraftPayload.model_validate(raw)


def _draft_out(d: draft_model.DraftView) -> EngagementDraftOut:
    return EngagementDraftOut(
        id=d.id,
        created_by=d.created_by,
        client_id=d.client_id,
        client_entity_id=d.client_entity_id,
        type_code=cast(CatalogueTypeCode | None, d.type_code),
        step=cast(WizardStep, d.step),
        payload=_payload_out(d.payload),
        prospect_engagement_id=d.prospect_engagement_id,
        gates=_gates_out(d.gates),
        version=d.version,
        saved_at=d.saved_at,
        allowed_actions=["engagement.create"],
    )


def _payload_in(p: EngagementDraftPayload | None) -> dict[str, object]:
    return {} if p is None else p.model_dump(mode="json", exclude_none=True)


# Listed before the live `router` in `api.ROUTERS`, so `/index` wins over `/{engagement_id}`.
engagements_v2_router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])
engagement_types_router = AbacusRouter(prefix="/v1/engagement-types", tags=["engagements"])
engagement_drafts_router = AbacusRouter(prefix="/v1/engagement-drafts", tags=["engagements"])


@engagements_v2_router.get(
    "/index", action="engagement.read_metadata", response_model=EngagementIndexPage
)
async def engagement_index_route(
    ctx: Ctx,
    service_line: Annotated[ServiceLine | None, Query()] = None,
    status: Annotated[EngagementStatus | None, Query()] = None,
    tile: Annotated[EngagementStatus | None, Query()] = None,
    office_id: Annotated[UUID | None, Query()] = None,
    partner_id: Annotated[UUID | None, Query()] = None,
    letter: Annotated[LetterRecordStatus | None, Query()] = None,
    next_due: Annotated[NextDueWindow | None, Query()] = None,
    period: Annotated[PeriodFilter, Query()] = "current",
    client_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> EngagementIndexPage:
    """ENG-01 and CLI-02's Engagements tab: past due first, then by next deadline. "Letter │ Not
    signed" lists Accepted engagements without a recorded letter (never a Prospect)."""
    page, summary = await index_model.engagement_index(
        ctx,
        index_model.IndexFilters(
            service_line=service_line,
            status=None if status is None else status.value,
            tile=None if tile is None else tile.value,
            office_id=office_id,
            partner_id=partner_id,
            letter=None if letter is None else letter.value,
            next_due=next_due,
            period=period,
            client_id=client_id,
            q=q,
        ),
        cursor=cursor,
        limit=limit,
    )
    return EngagementIndexPage(
        items=[_index_row(r) for r in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
        total_capped=page.total_capped,
        counts=page.counts,
        facets=page.facets,
        summary=EngagementIndexSummaryOut(
            prospect=summary.prospect,
            awaiting_letter=summary.awaiting_letter,
            past_due=summary.past_due,
        ),
    )


@engagements_v2_router.get(
    "/{engagement_id}/record",
    action="engagement.read_metadata",
    response_model=EngagementRecordOut,
)
async def engagement_record_route(engagement_id: UUID, ctx: Ctx) -> EngagementRecordOut:
    """ENG-02: 404 for a walled or unknown engagement or a client principal."""
    return _record_out(await record_model.engagement_record(ctx, engagement_id))


@engagements_v2_router.get(
    "/{engagement_id}/gates",
    action="engagement.read_metadata",
    response_model=list[EngagementGateOut],
)
async def engagement_gates_route(engagement_id: UUID, ctx: Ctx) -> list[EngagementGateOut]:
    """`[{gate, met, blockers}]` for the registered providers (C1 v1.1)."""
    return _gates_out(await record_model.engagement_gates_v2(ctx, engagement_id))


# --- ENG-02 status menu: Active ⇄ On hold (TASK-1198; DEC-328) ----------------------------------


class EngagementHoldIn(BaseModel):
    """ "On hold…" names a reason code, never free text (§3.1.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[HoldReason, classified("internal")]


class EngagementStatusOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    status: Annotated[EngagementStatus, classified("internal")]  # C2
    hold_reason: Annotated[HoldReason | None, classified("internal")] = None


@engagements_v2_router.post(
    "/{engagement_id}/hold",
    action="engagement.hold",
    response_model=EngagementStatusOut,
    errors=(409,),
)
async def hold_engagement_route(
    engagement_id: UUID, body: EngagementHoldIn, ctx: Ctx
) -> EngagementStatusOut:
    """A person, with fresh MFA: Active → On hold with a reason; `engagement.held` audited and
    `engagement.status_changed` emitted in one unit of work. 409 `illegal_transition` from any
    other state (archived included)."""
    await transitions.hold(ctx, engagement_id, body.reason)
    return EngagementStatusOut(
        engagement_id=engagement_id, status=EngagementStatus.ON_HOLD, hold_reason=body.reason
    )


@engagements_v2_router.post(
    "/{engagement_id}/resume",
    action="engagement.hold",
    response_model=EngagementStatusOut,
    errors=(409,),
)
async def resume_engagement_route(engagement_id: UUID, ctx: Ctx) -> EngagementStatusOut:
    """On hold → Active; `engagement.resumed`. 409 `illegal_transition` unless on hold."""
    await transitions.resume(ctx, engagement_id)
    return EngagementStatusOut(engagement_id=engagement_id, status=EngagementStatus.ACTIVE)


@engagements_v2_router.put(
    "/{engagement_id}/letter/record",
    action="letter.record",
    response_model=EngagementLetterRecordOut,
    errors=(409,),
)
async def record_engagement_letter_route(
    engagement_id: UUID, body: LetterRecordIn, ctx: Ctx
) -> EngagementLetterRecordOut:
    """Human-only. The interim G3 provider until C7: 409 `gate_unmet` (G1), 409
    `letter_before_acceptance`, 409 `engagement_archived`, 409 `letter_exceptions_off` for the
    exception unless the firm has `allow_letter_exceptions` on and the caller is the engagement
    partner, 422 `letter_exception_reason_required` without a reason; one `letter.recorded`
    audit event. The exception reads `mode: not_required_this_year`."""
    done = await record_model.record_letter_v2(
        ctx,
        engagement_id,
        record_model.RecordedLetterIn(
            mode=body.mode,
            client_signed_on=body.client_signed_on,
            firm_signed_on=body.firm_signed_on,
            client_signer_contact_id=body.client_signer_contact_id,
            firm_signer_user_id=body.firm_signer_user_id,
            signed_copy_version_id=body.signed_copy_version_id,
            not_required_reason=body.not_required_reason,
        ),
    )
    letter = done.letter
    return EngagementLetterRecordOut(
        engagement_id=engagement_id,
        status=LetterRecordStatus.SIGNED,
        mode=body.mode,
        client_signed_on=letter.client_signed_on,
        firm_signed_on=letter.firm_signed_on,
        client_signer_contact_id=letter.client_signer_contact_id,
        firm_signer_user_id=letter.firm_signer_user_id,
        signed_copy_version_id=letter.signed_copy_version_id,
        acceptance_decided_at=done.acceptance_decided_at,
        recorded_by=ctx.user_id,
        recorded_at=letter.recorded_at,
        engagement_status=EngagementStatus(done.engagement_status),
    )


@engagement_types_router.get(
    "", action="engagement.create", response_model=EngagementTypeCatalogueOut
)
async def engagement_types_route(ctx: Ctx) -> EngagementTypeCatalogueOut:
    """The selectable catalogue; an entitlement-gated card (SOC 1, SOC 2) is `needs_entitlement`
    without `attest`. Never `single_audit`."""
    return EngagementTypeCatalogueOut(
        items=[
            EngagementTypeEntryOut(
                code=cast(CatalogueTypeCode, i.entry.code),
                engagement_type=cast(EngagementType, i.entry.engagement_type),
                family=i.entry.family,
                work_item_kind=cast(WorkItemKind, i.entry.work_item_kind),
                label=i.entry.label,
                standard_line=i.entry.standard_line,
                availability="available" if i.available else "needs_entitlement",
                entitlement=i.entry.entitlement,
                group_audit_allowed=i.entry.group_audit_allowed,
                steps=[
                    EngagementTypeStepOut(step=step, field_codes=list(fields))
                    for step, fields in i.steps
                ],
            )
            for i in await draft_model.catalogue(ctx)
        ]
    )


@engagement_drafts_router.post(
    "",
    action="engagement.create",
    response_model=EngagementDraftOut,
    status_code=201,
)
async def create_engagement_draft_route(body: EngagementDraftIn, ctx: Ctx) -> EngagementDraftOut:
    """422 `unknown_engagement_type` for a code outside the catalogue."""
    return _draft_out(
        await draft_model.create_draft(
            ctx,
            client_id=body.client_id,
            client_entity_id=body.client_entity_id,
            type_code=body.type_code,
            step=body.step,
            payload=_payload_in(body.payload),
        )
    )


@engagement_drafts_router.get(
    "/{draft_id}", action="engagement.create", response_model=EngagementDraftOut
)
async def get_engagement_draft_route(draft_id: UUID, ctx: Ctx) -> EngagementDraftOut:
    """The owner's own draft; anyone else's answers 404."""
    return _draft_out(await draft_model.get_draft(ctx, draft_id))


@engagement_drafts_router.patch(
    "/{draft_id}",
    action="engagement.create",
    response_model=EngagementDraftOut,
    errors=(409,),
)
async def update_engagement_draft_route(
    draft_id: UUID, body: EngagementDraftPatchIn, ctx: Ctx
) -> EngagementDraftOut:
    return _draft_out(
        await draft_model.update_draft(
            ctx,
            draft_id,
            body.seen_version,
            draft_model.DraftChange(
                client_id=body.client_id,
                client_entity_id=body.client_entity_id,
                type_code=body.type_code,
                step=body.step,
                payload=None if body.payload is None else _payload_in(body.payload),
            ),
        )
    )


@engagement_drafts_router.delete(
    "/{draft_id}",
    action="engagement.create",
    response_model=EngagementDraftDiscardedOut,
)
async def discard_engagement_draft_route(draft_id: UUID, ctx: Ctx) -> EngagementDraftDiscardedOut:
    """ "Discard this draft?" (purged 30 days later, OQ-17)."""
    at = await draft_model.discard_draft(ctx, draft_id)
    return EngagementDraftDiscardedOut(draft_id=draft_id, discarded_at=at)


@engagement_drafts_router.post(
    "/{draft_id}/validate",
    action="engagement.create",
    response_model=EngagementDraftValidationOut,
)
async def validate_engagement_draft_route(
    draft_id: UUID, body: DraftValidateIn, ctx: Ctx
) -> EngagementDraftValidationOut:
    v = await draft_model.validate_draft(ctx, draft_id, body.step)
    return EngagementDraftValidationOut(
        draft_id=draft_id,
        step=body.step,
        valid=v.valid,
        problems=[DraftProblemOut(field=p.field, code=p.code) for p in v.problems],
        gates=_gates_out(v.gates),
    )


@engagement_drafts_router.post(
    "/{draft_id}/start-acceptance",
    action="client.intake",
    response_model=AcceptanceStartedOut,
    status_code=201,
    errors=(409,),
)
async def start_acceptance_from_draft_route(draft_id: UUID, ctx: Ctx) -> AcceptanceStartedOut:
    """Human-only (OQ-2): a Prospect engagement and an acceptance record; nothing is accepted
    (P-07-T35, DEC-372). 409
    `acceptance_template_missing`, 422 `draft_incomplete`."""
    await _intake_gate(ctx)
    started = await draft_model.start_acceptance(ctx, draft_id)
    return AcceptanceStartedOut(
        draft_id=started.draft_id,
        engagement_id=started.engagement_id,
        acceptance_record_id=started.acceptance_record_id,
        engagement_status=EngagementStatus(started.engagement_status),
    )


@engagement_drafts_router.post(
    "/{draft_id}/create",
    action="engagement.create",
    response_model=EngagementFromDraftOut,
    status_code=201,
    errors=(409,),
)
async def create_engagement_from_draft_route(
    draft_id: UUID, body: DraftCreateIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EngagementFromDraftOut:
    """Human-only, one unit of work: 409 `possible_duplicate` until `confirm_duplicate`, 409
    `gate_unmet` (G1), 422 `unknown_engagement_type`, 422 `draft_incomplete`."""
    await draft_model.check_create(ctx, draft_id)

    async def run() -> tuple[int, dict[str, object]]:
        made = await draft_model.create_from_draft(
            ctx, draft_id, confirm_duplicate=body.confirm_duplicate
        )
        out = EngagementFromDraftOut(
            engagement_id=made.engagement_id,
            engagement_status=EngagementStatus(made.engagement_status),
            work_item_ids=made.work_item_ids,
            independence_requested_user_ids=made.independence_requested_user_ids,
            methodology_version_id=made.methodology_version_id,
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="engagement_drafts.create",
        key=idempotency_key,
        body={"draft_id": str(draft_id), **body.model_dump(mode="json")},
        run=run,
    )
    return EngagementFromDraftOut.model_validate(stored.body)
