"""The notices v1 contract stub (N-04-T02; N-04 §4.3; DEC-2051).
Contract: `docs/contracts/notices.md` (freeze Fri Oct 29, 2027); screens NOT-01, NOT-02, NOT-03;
consumers CLI-05, HOME-01, HOME-02, POR-02 (through the portal's home source, never these routes).

Every IRS and state notice as a `notice` work item: its intake (read by code maps, the agent for
types without a map, or a person), the comparison of the notice, the return as filed and the
information returns, the partner's position (P-04's `notice_position` decision; there is no
notices decide route), the response letter from the firm's template and its send. Every route
answers, in order: a client principal 404 (INV-4: the portal sees only the C7 envelope, the
payment-confirmation request and the POR-02 row, each through its own grant); the matrix action on
the notice's engagement (or the firm for lists and intakes); 404 with `notices.workspace` off; 501
`not_implemented` until N-04-T06 onward. Amounts and lines are tax return information (`tri`);
TINs and confirmation numbers are sealed and only their last four digits travel.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import NOTICES_WORKSPACE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
Tri = classified("restricted", tri=True)
Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2), Tri]
Last4 = Annotated[str, Field(pattern=r"^\d{4}$"), classified("confidential")]
Code = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), classified("internal")]

Agency = Literal["irs", "state"]
NoticeTypeKey = Literal[
    "cp2000", "cp14", "cp501", "cp503", "cp504", "cp3219a", "state_generic", "unknown"
]
NoticeStatus = Literal[
    "received",
    "classified",
    "analyzing",
    "response_drafted",
    "approved",
    "sent",
    "awaiting_irs",
    "closed",
    "escalated",
]  # C2's `notice` object (status-vocabulary.yaml)
Tile = Literal["new", "analyzing", "response_drafted", "awaiting"]  # QN-6 mapping, §4.2
IntakeStatus = Literal["extracting", "ready", "manual_entry", "created", "discarded", "failed"]
IntakeSource = Literal["upload", "inbox", "portal", "organizer"]
ExtractionMode = Literal["code_map", "agent", "manual"]
FieldOrigin = Literal["code_map", "agent", "human"]
AuthorizationKind = Literal["form_8821", "form_2848", "state_poa", "none"]
Position = Literal["agree", "partially_agree", "disagree"]
AgentStage = Literal["off", "shadow", "live", "refused"]
RiskBand = Literal["red", "amber", "none"]  # respond-by within 7 days, within 30, otherwise
AnalysisKind = Literal["underreporter_comparison", "balance_due", "none"]
AnalysisStatus = Literal["running", "ready", "failed", "superseded"]
Readiness = Literal[
    "waiting_decision", "in_review", "approved", "out_for_signature", "ready_to_send", "sent"
]
Channel = Literal["dut", "fax", "mail"]
PaymentMethod = Literal["irs_direct_pay", "eftps", "state_portal", "check", "later_bill"]
BlockOrigin = Literal["template", "human", "agent"]
NoticeAction = Literal[
    "notice.assign",
    "notice.update",
    "notice.start",
    "notice.record_as_filed",
    "notice.analyze",
    "notice.request_decision",
    "notice.note",
    "notice.agency_reply",
    "notice_response.draft",
    "notice_response.edit",
    "notice_response.send_for_signature",
    "notice_response.mark_sent",
]
Actions = Annotated[list[NoticeAction], classified("internal")]
FieldKey = Literal[
    "notice.code",
    "notice.tax_year",
    "notice.form",
    "notice.date",
    "notice.respond_by",
    "notice.amount_tax",
    "notice.amount_interest",
    "notice.amount_penalty",
    "notice.amount_total",
    "notice.interest_to",
    "notice.response_page",
    "taxpayer.name",
    "taxpayer.tin",
    "agency.name",
]


# --- shared facts -------------------------------------------------------------------------------


class AuthorizationOut(BaseModel):
    """The authorization on file for the form and year (T-01's register): NOT-01's column,
    NOT-02's card. `can_represent` is code's (a Form 2848 for the form and year)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[AuthorizationKind, classified("internal")]
    label: Annotated[str, classified("internal")]  # "8821 ✓", "CO POA ✓", "None · blocked"
    on_file: Annotated[bool, classified("internal")]
    can_represent: Annotated[bool, classified("internal")]
    authorization_id: Annotated[UUID | None, classified("internal")] = None


class AmountsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tax: Money | None = None
    interest: Money | None = None
    penalty: Money | None = None
    total: Money | None = None
    interest_to: Annotated[date | None, classified("internal")] = None


class NoticePersonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    initials: Annotated[str, Field(max_length=4), classified("internal")]


# --- NOT-01 index and summary -------------------------------------------------------------------


class NoticeRowOut(BaseModel):
    """One NOT-01 row (N1: Marcus & Dana Whitley · IRS · CP2000 · Proposed adjustment · 2024 ·
    Aug 24 · Sep 23 · 9 days · $686.40 + $66.61 interest · Analyzing · KO · 8821 ✓)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]  # the notice's work item
    engagement_id: Annotated[UUID, classified("internal")]
    client_entity_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    form_line: Annotated[str | None, classified("internal")]  # "Form 1040"
    agency: Annotated[Agency, classified("internal")]
    agency_name: Annotated[str, classified("internal")]  # "IRS", "Colorado DOR"
    notice_type_key: Annotated[NoticeTypeKey, classified("internal")]
    notice_code: Annotated[str, classified("internal")]  # "CP2000", "DTF-160"
    title: Annotated[str, classified("internal")]  # "Proposed adjustment"
    tax_year: Annotated[int, Field(ge=1990, le=2100), classified("internal")]
    received_on: Annotated[date, classified("internal")]
    respond_by: Annotated[date | None, classified("internal")]
    respond_by_days: Annotated[int | None, classified("internal")]  # from the demo clock
    risk: Annotated[RiskBand, classified("internal")]
    sent_on: Annotated[date | None, classified("internal")]  # "Response sent Aug 12"
    amounts: AmountsOut
    position: Annotated[Position | None, classified("internal")]  # "· disagreed"
    status: Annotated[NoticeStatus, classified("internal")]
    tile: Annotated[Tile | None, classified("internal")]  # escalated rows have none
    assignee: NoticePersonOut | None
    authorization: AuthorizationOut
    version: Annotated[int, Field(ge=1), classified("internal")]


class TypeCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]  # cp2000, cp14, cp501, state
    label: Annotated[str, classified("internal")]  # "CP2000", "State"
    count: Annotated[int, Field(ge=0), classified("internal")]


class NoticesSummaryOut(BaseModel):
    """NOT-01's tiles and summary line, tallied from the viewer's visible rows only (DEC-43):
    2 New · 3 Analyzing · 2 Response drafted · 2 Awaiting IRS; 3 CP2000 · 2 CP14 · 1 CP501 · 3
    State; "9 open · 1 due within 7 days · 1 blocked (no authorization)"."""

    model_config = ConfigDict(frozen=True)

    tiles: Annotated[dict[Tile, int], classified("internal")]
    by_type: Annotated[list[TypeCountOut], classified("internal")]
    open: Annotated[int, Field(ge=0), classified("internal")]
    due_within_7: Annotated[int, Field(ge=0), classified("internal")]
    blocked: Annotated[int, Field(ge=0), classified("internal")]  # no authorization on file
    agent_stage: Annotated[AgentStage, classified("internal")]  # the chip: Off · Shadow · Live


# --- intake (NOT-01 b, c, d) --------------------------------------------------------------------


class IntakeSourceIn(BaseModel):
    """An intake from an inbox item or an evidence version already stored. The multipart upload
    variant (to the N-01 inbox, channel `manual`) is declared with the intake service (N-04-T07),
    DEC-2051."""

    model_config = ConfigDict(extra="forbid")

    source: Annotated[IntakeSource, classified("internal")]
    inbox_item_id: Annotated[UUID | None, classified("internal")] = None
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None


class RegionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: Annotated[int, Field(ge=1), classified("internal")]
    bbox: Annotated[list[float], Field(min_length=4, max_length=4), classified("internal")]


class IntakeFieldOut(BaseModel):
    """A field with its confidence pill (green-tint at 0.95 and above, amber below) and origin.
    A TIN travels as its last four only; the sealed value never leaves the server."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[FieldKey, classified("internal")]
    value_text: Annotated[str | None, Tri]
    last4: Last4 | None = None
    confidence: Annotated[
        Decimal | None, Field(ge=0, le=1, decimal_places=3), classified("internal")
    ]
    low_confidence: Annotated[bool, classified("internal")]
    note: Annotated[str | None, classified("internal")] = None  # "date partly obscured"
    helper: Annotated[str | None, classified("internal")] = None  # "Check page 1, top right"
    origin: Annotated[FieldOrigin, classified("internal")]
    confirmed: Annotated[bool, classified("internal")]
    region: RegionOut | None = None
    citation_id: Annotated[UUID | None, classified("internal")] = None


class MatchCandidateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_entity_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    tin_last4: Last4 | None = None


class MatchOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_entity_id: Annotated[UUID | None, classified("internal")]
    client_name: Annotated[str | None, classified("confidential")]
    method: Annotated[Literal["name_tin", "tin", "name", "manual"] | None, classified("internal")]
    candidates: Annotated[
        list[MatchCandidateOut], Field(max_length=20), classified("confidential")
    ]
    return_id: Annotated[UUID | None, classified("internal")]
    return_label: Annotated[str | None, classified("internal")]  # "TY2024 Form 1040 · Accepted"
    office: Annotated[str | None, classified("internal")]


class IntakeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[IntakeStatus, classified("internal")]
    source: Annotated[IntakeSource, classified("internal")]
    file_name: Annotated[str | None, classified("confidential")]
    pages: Annotated[int | None, Field(ge=1), classified("internal")]
    uploaded_by_label: Annotated[str | None, classified("confidential")]
    extraction_mode: Annotated[ExtractionMode | None, classified("internal")]
    manual_reason: Annotated[str | None, classified("internal")] = None  # in words, never guessed
    fields: Annotated[list[IntakeFieldOut], Field(max_length=40), Tri]
    match: MatchOut
    authorization: AuthorizationOut
    duplicate_of: Annotated[UUID | None, classified("internal")] = None  # "Looks like N2"
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    notify_user_ids: Annotated[list[UUID], classified("internal")] = []
    created_work_item_id: Annotated[UUID | None, classified("internal")] = None
    version: Annotated[int, Field(ge=1), classified("internal")]


class NoticeFieldEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[FieldKey, classified("internal")]
    value_text: Annotated[str | None, Field(max_length=200), Tri] = None
    tin: Annotated[
        str | None, Field(pattern=r"^\d{9}$"), classified("restricted", pii_kind="tin")
    ] = None
    confirm: Annotated[bool, classified("internal")] = False  # a low-confidence value accepted


class IntakeUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: Annotated[list[NoticeFieldEditIn], Field(max_length=40), Tri] = []
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    related_return_id: Annotated[UUID | None, classified("internal")] = None
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    notify_user_ids: Annotated[list[UUID] | None, Field(max_length=20), classified("internal")] = (
        None
    )


class IntakeCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_entity_id: Annotated[UUID, classified("internal")]
    related_return_id: Annotated[UUID | None, classified("internal")] = None
    assignee_id: Annotated[UUID, classified("internal")]
    notify_user_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    create_anyway: Annotated[bool, classified("internal")] = False  # past a possible duplicate


class IntakeAttachIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice_id: Annotated[UUID, classified("internal")]


class IntakeDiscardIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Code


class CreatedNoticeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    notice_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]


# --- NOT-02 detail, analysis, decision ----------------------------------------------------------


class ReadinessFactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]  # decision, sign_offs, signatures, payment
    met: Annotated[bool, classified("internal")]
    label: Annotated[str, classified("internal")]


class NoticeOut(BaseModel):
    """NOT-02's header and NOT-03's ladder facts; `allowed_actions` per viewer."""

    model_config = ConfigDict(frozen=True)

    row: NoticeRowOut
    notice_date: Annotated[date | None, classified("internal")]
    respond_by_source: Annotated[
        Literal["extracted", "entered", "corrected"] | None, classified("internal")
    ]
    taxpayer_tin_last4: Last4 | None = None
    related_return_id: Annotated[UUID | None, classified("internal")]
    related_return_label: Annotated[str | None, classified("internal")]
    partner_owned: Annotated[bool, classified("internal")]
    signer: NoticePersonOut | None
    decision_id: Annotated[UUID | None, classified("internal")]
    decided_by: NoticePersonOut | None
    decided_at: Annotated[datetime | None, classified("internal")]
    follow_up_on: Annotated[date | None, classified("internal")]
    closed_on: Annotated[date | None, classified("internal")]
    escalated_reason: Annotated[str | None, classified("confidential")]
    client_visible: Annotated[bool, classified("internal")]
    readiness: Annotated[list[ReadinessFactOut], classified("internal")]
    allowed_actions: Actions


class NoticePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_id: Annotated[UUID | None, classified("internal")] = None
    respond_by: Annotated[date | None, classified("internal")] = None  # corrected
    related_return_id: Annotated[UUID | None, classified("internal")] = None
    client_visible: Annotated[bool | None, classified("internal")] = None


class CitedLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    label: Annotated[str | None, Field(max_length=200), classified("internal")] = None
    value: Money
    citation_id: Annotated[UUID, classified("internal")]  # every entered line is cited


class ReturnAsFiledIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[Literal["entry", "engine_import"], classified("internal")]
    filing_status: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    filed_on: Annotated[date | None, classified("internal")] = None
    lines: Annotated[list[CitedLineIn], Field(max_length=200), Tri] = []


class ProposedItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[Literal["line_change", "payer_item"], classified("internal")]
    line_key: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    label: Annotated[str, Field(min_length=1, max_length=200), classified("internal")]
    payer_name: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    info_form: Annotated[str | None, Field(max_length=20), classified("internal")] = None
    amount_shown: Money | None = None
    amount_irs: Money | None = None
    citation_id: Annotated[UUID, classified("internal")]


class ProposedItemsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[ProposedItemIn], Field(min_length=1, max_length=200), Tri]


class AnalysisRowOut(BaseModel):
    """One statement row: notice vs return vs information returns, by code."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    as_filed: Money | None = None
    irs: Money | None = None
    information_returns: Money | None = None
    difference: Money | None = None
    citation_ids: Annotated[list[UUID], classified("internal")]


class InformationReturnOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    payer_name: Annotated[str, classified("confidential")]
    form: Annotated[str, classified("internal")]  # "1099-INT"
    amount: Money
    on_return: Annotated[bool, classified("internal")]
    issued_after_filing: Annotated[bool, classified("internal")]
    document_id: Annotated[UUID | None, classified("internal")]
    citation_id: Annotated[UUID | None, classified("internal")]


class BracketCheckOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rate: Annotated[Decimal, classified("internal")]  # 0.22
    expected: Money  # 22% x 3,120 = 686.40
    notice: Money
    agrees: Annotated[bool, classified("internal")]
    reason: Annotated[str | None, classified("internal")]


class AnalysisChecksOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    difference_explained: Annotated[bool, classified("internal")]
    bracket_check: BracketCheckOut | None
    total_foots: Annotated[bool, classified("internal")]


class NoticeSourceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("internal")]
    document_ids: Annotated[list[UUID], classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]


class AgentBlockOut(BaseModel):
    """The AgentBlock: live, shadow (recorded, not shown), off or refused (with the reason in
    words: "Agents can't read this taxpayer's return information — §7216 consents missing")."""

    model_config = ConfigDict(frozen=True)

    stage: Annotated[AgentStage, classified("internal")]
    run_id: Annotated[UUID | None, classified("internal")]
    explanation: Annotated[str | None, Tri]  # rendered through AgentText only
    recommended_position: Annotated[Position | None, classified("internal")]
    refusal: Annotated[str | None, classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[AnalysisStatus, classified("internal")]
    analysis_kind: Annotated[AnalysisKind, classified("internal")]
    progress_label: Annotated[str | None, classified("internal")]  # "Comparing 6 information …"
    rows: Annotated[list[AnalysisRowOut], Tri]
    information_returns: Annotated[list[InformationReturnOut], Tri]
    transcript_rows: Annotated[list[AnalysisRowOut], Tri]  # T-01's comparisons (live segment)
    checks: AnalysisChecksOut | None
    sources: Annotated[list[NoticeSourceOut], classified("internal")]
    agent: AgentBlockOut
    decision_card_id: Annotated[UUID | None, classified("internal")]
    engine_name: Annotated[str, classified("internal")]
    engine_version: Annotated[str, classified("internal")]
    inputs_hash: Annotated[str, classified("internal")]


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[AnalysisStatus, classified("internal")]
    reused: Annotated[bool, classified("internal")]  # same inputs_hash: the existing version


class DecisionRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[str | None, Field(max_length=4000), Tri] = None


class DecisionRequestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID, classified("internal")]


class NoticeNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=4000), Tri]
    decision_card_id: Annotated[UUID | None, classified("internal")] = None


class NoticeNoteOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    author: NoticePersonOut
    created_at: Annotated[datetime, classified("internal")]


class ActivityItemOut(BaseModel):
    """NOT-02 a2: "Received Aug 24 · Uploaded by Dana via portal · Classified · Analyzed ·
    Decision requested"; agent output reads "Kevin Osei via Agent" (INV-5)."""

    model_config = ConfigDict(frozen=True)

    at: Annotated[datetime, classified("internal")]
    event: Annotated[str, classified("internal")]  # the audit action
    label: Annotated[str, classified("internal")]
    actor_label: Annotated[str | None, classified("confidential")]


# --- NOT-03 response ----------------------------------------------------------------------------


class BlockOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    origin: Annotated[BlockOrigin, classified("internal")]
    template_block_key: Annotated[str | None, classified("internal")]
    text: Annotated[str, Tri]
    edited: Annotated[bool, classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]


class EnclosureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: Annotated[int, Field(ge=1), classified("internal")]
    label: Annotated[str, classified("confidential")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    on: Annotated[bool, classified("internal")]
    required: Annotated[bool, classified("internal")]


class PaymentOut(BaseModel):
    """The Payment band: a method label, never an instrument (ADR P-27)."""

    model_config = ConfigDict(frozen=True)

    amounts: AmountsOut
    method_label: Annotated[PaymentMethod | None, classified("internal")]
    paid_on: Annotated[date | None, classified("internal")]
    confirmation_request_item_id: Annotated[UUID | None, classified("internal")]
    request_state: Annotated[str | None, classified("internal")]


class ApprovalStepOut(BaseModel):
    """P-04's ladder: Prepared KO ✓ · Reviewed SI in progress · Approved DR ring."""

    model_config = ConfigDict(frozen=True)

    level: Annotated[str, classified("internal")]
    person: NoticePersonOut | None
    state: Annotated[Literal["done", "in_progress", "pending", "stale"], classified("internal")]


class ResponseOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    template_key: Annotated[str, classified("internal")]
    position: Annotated[Position | None, classified("internal")]
    position_source: Annotated[Literal["decided", "provisional"], classified("internal")]
    position_mismatch: Annotated[bool, classified("internal")]  # "Regenerate for Disagree"
    blocks: Annotated[list[BlockOut], Tri]
    enclosures: Annotated[list[EnclosureOut], classified("confidential")]
    payment: PaymentOut | None
    signer_contact_ids: Annotated[list[UUID], classified("internal")]
    channel: Annotated[Channel | None, classified("internal")]
    follow_up_days: Annotated[int, Field(ge=1, le=365), classified("internal")]
    owner: NoticePersonOut | None
    approvals: Annotated[list[ApprovalStepOut], classified("internal")]
    readiness: Annotated[Readiness, classified("internal")]
    readiness_facts: Annotated[list[ReadinessFactOut], classified("internal")]
    envelope_id: Annotated[UUID | None, classified("internal")]
    envelope_status: Annotated[str | None, classified("internal")]  # C7's words
    locked: Annotated[bool, classified("internal")]  # after send (`response_locked`)
    row_version: Annotated[int, Field(ge=1), classified("internal")]


class BlockEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    text: Annotated[str, Field(min_length=1, max_length=8000), Tri]


class EnclosureToggleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: Annotated[int, Field(ge=1), classified("internal")]
    on: Annotated[bool, classified("internal")]


class ResponseEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks: Annotated[list[BlockEditIn], Field(max_length=60), Tri] = []
    enclosures: Annotated[
        list[EnclosureToggleIn], Field(max_length=40), classified("internal")
    ] = []
    payment_method: Annotated[PaymentMethod | None, classified("internal")] = None
    signer_contact_ids: Annotated[
        list[UUID] | None, Field(max_length=4), classified("internal")
    ] = None
    channel: Annotated[Channel | None, classified("internal")] = None
    follow_up_days: Annotated[int | None, Field(ge=1, le=365), classified("internal")] = None
    owner_user_id: Annotated[UUID | None, classified("internal")] = None


class SendForSignatureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    envelope_id: Annotated[UUID, classified("internal")]  # opens SIG-02 d
    confirmation_request_item_id: Annotated[UUID | None, classified("internal")]


class MarkSentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Annotated[Channel, classified("internal")]
    confirmation_no: Annotated[
        str | None, Field(min_length=4, max_length=40), classified("restricted", tri=True)
    ] = None  # sealed on write; only its last four come back
    sent_on: Annotated[date, classified("internal")]
    follow_up_days: Annotated[int | None, Field(ge=1, le=365), classified("internal")] = None


class SentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sent_on: Annotated[date, classified("internal")]
    follow_up_on: Annotated[date, classified("internal")]
    confirmation_last4: Last4 | None = None


class AgencyReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Annotated[Literal["resolved", "escalated"], classified("internal")]
    closed_on: Annotated[date | None, classified("internal")] = None
    note: Annotated[str | None, Field(max_length=4000), Tri] = None
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    escalated_reason: Annotated[str | None, Field(max_length=500), classified("confidential")] = (
        None
    )


# --- gates and routes ---------------------------------------------------------------------------


async def _gate_flag(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("notices")
    if not await flag_enabled(ctx.tenant, NOTICES_WORKSPACE):
        raise NotFound(NOTICES_WORKSPACE.name)


async def _gate_firm(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("notices")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, NOTICES_WORKSPACE):
        raise NotFound(NOTICES_WORKSPACE.name)


async def _gate(ctx: AuthContext, notice_id: UUID, action: str) -> None:
    if ctx.client:
        raise NotFound("notices")
    engagement_id = await work_item_engagement(ctx.tenant, notice_id)
    if engagement_id is None:
        raise NotFound("notice")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, NOTICES_WORKSPACE):
        raise NotFound(NOTICES_WORKSPACE.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1", tags=["notices"])
_N = "/notices/{notice_id}"
_I = "/notice-intakes/{intake_id}"


@router.get("/notices", action="notice.read", response_model=ListPage[NoticeRowOut], errors=(501,))
async def notices_route(
    ctx: Ctx,
    agency: Agency | None = None,
    type: NoticeTypeKey | None = None,  # the query parameter's name (§4.3)
    assignee: UUID | None = None,
    respond_by: Literal[7, 30] | None = None,
    status: NoticeStatus | None = None,
    tile: Tile | None = None,
    client_entity_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
) -> ListPage[NoticeRowOut]:
    """Rows by deadline risk (respond-by ascending; sent rows after), visible rows only."""
    await _gate_firm(ctx, "notice.read")
    _not_yet()


@router.get(
    "/notices/summary", action="notice.read", response_model=NoticesSummaryOut, errors=(501,)
)
async def notices_summary_route(ctx: Ctx) -> NoticesSummaryOut:
    await _gate_firm(ctx, "notice.read")
    _not_yet()


@router.post(
    "/notice-intakes",
    action="notice_intake.create",
    response_model=IntakeOut,
    status_code=202,
    errors=(409, 501),
)
async def intake_create_route(
    body: IntakeSourceIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeOut:
    """Starts NoticeIntakeWorkflow; the sheet polls while `extracting`."""
    await _gate_firm(ctx, "notice_intake.create")
    _not_yet()


@router.get(_I, action="notice_intake.read", response_model=IntakeOut, errors=(501,))
async def intake_route(intake_id: UUID, ctx: Ctx) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.read")
    _not_yet()


@router.put(_I, action="notice_intake.update", response_model=IntakeOut, errors=(409, 501))
async def intake_update_route(
    intake_id: UUID, body: IntakeUpdateIn, ctx: Ctx, if_match: IfMatch
) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.update")
    _not_yet()


@router.post(
    f"{_I}/create",
    action="notice_intake.confirm",
    response_model=CreatedNoticeOut,
    status_code=201,
    errors=(409, 501),
)
async def intake_confirm_route(
    intake_id: UUID, body: IntakeCreateIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> CreatedNoticeOut:
    """409 `low_confidence_unconfirmed`, `duplicate_unresolved`, `no_client`."""
    await _gate_firm(ctx, "notice_intake.confirm")
    _not_yet()


@router.post(
    f"{_I}/attach", action="notice_intake.confirm", response_model=IntakeOut, errors=(409, 501)
)
async def intake_attach_route(
    intake_id: UUID, body: IntakeAttachIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.confirm")
    _not_yet()


@router.post(
    f"{_I}/discard", action="notice_intake.confirm", response_model=IntakeOut, errors=(409, 501)
)
async def intake_discard_route(
    intake_id: UUID, body: IntakeDiscardIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.confirm")
    _not_yet()


@router.get(_N, action="notice.read", response_model=NoticeOut, errors=(501,))
async def notice_route(notice_id: UUID, ctx: Ctx) -> NoticeOut:
    await _gate(ctx, notice_id, "notice.read")
    _not_yet()


@router.patch(_N, action="notice.update", response_model=NoticeOut, errors=(409, 501))
async def notice_patch_route(
    notice_id: UUID, body: NoticePatchIn, ctx: Ctx, if_match: IfMatch
) -> NoticeOut:
    """`notice.assign` for `assignee_id` alone, `notice.update` otherwise (the service checks)."""
    await _gate(ctx, notice_id, "notice.assign" if _assign_only(body) else "notice.update")
    _not_yet()


def _assign_only(body: NoticePatchIn) -> bool:
    return body.model_fields_set == {"assignee_id"}


@router.post(f"{_N}:start", action="notice.start", response_model=NoticeOut, errors=(409, 501))
async def notice_start_route(
    notice_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> NoticeOut:
    """received to classified, and the analysis starts."""
    await _gate(ctx, notice_id, "notice.start")
    _not_yet()


@router.put(
    f"{_N}/return-as-filed",
    action="notice.record_as_filed",
    response_model=AnalysisRunOut,
    errors=(409, 501),
)
async def return_as_filed_route(
    notice_id: UUID, body: ReturnAsFiledIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AnalysisRunOut:
    await _gate(ctx, notice_id, "notice.record_as_filed")
    _not_yet()


@router.put(
    f"{_N}/proposed-items",
    action="notice.record_as_filed",
    response_model=AnalysisRunOut,
    errors=(409, 501),
)
async def proposed_items_route(
    notice_id: UUID, body: ProposedItemsIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AnalysisRunOut:
    await _gate(ctx, notice_id, "notice.record_as_filed")
    _not_yet()


@router.get(f"{_N}/analysis", action="notice.read", response_model=AnalysisOut, errors=(501,))
async def analysis_route(notice_id: UUID, ctx: Ctx) -> AnalysisOut:
    await _gate(ctx, notice_id, "notice.read")
    _not_yet()


@router.post(
    f"{_N}/analysis/run",
    action="notice.analyze",
    response_model=AnalysisRunOut,
    status_code=202,
    errors=(409, 501),
)
async def analysis_run_route(
    notice_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AnalysisRunOut:
    """Idempotent on `inputs_hash`."""
    await _gate(ctx, notice_id, "notice.analyze")
    _not_yet()


@router.post(
    f"{_N}/decision-requests",
    action="notice.request_decision",
    response_model=DecisionRequestOut,
    status_code=201,
    errors=(409, 501),
)
async def decision_request_route(
    notice_id: UUID, body: DecisionRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DecisionRequestOut:
    """Raises or refreshes the `notice_position` card (P-04), reserved to the notice's signer;
    deciding is `POST /v1/decision-cards/{id}/decide`, never a notices route."""
    await _gate(ctx, notice_id, "notice.request_decision")
    _not_yet()


@router.post(
    f"{_N}/notes",
    action="notice.note",
    response_model=NoticeNoteOut,
    status_code=201,
    errors=(501,),
)
async def note_route(
    notice_id: UUID, body: NoticeNoteIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> NoticeNoteOut:
    await _gate(ctx, notice_id, "notice.note")
    _not_yet()


@router.get(
    f"{_N}/activity",
    action="notice.read",
    response_model=ListPage[ActivityItemOut],
    errors=(501,),
)
async def activity_route(
    notice_id: UUID, ctx: Ctx, cursor: str | None = None
) -> ListPage[ActivityItemOut]:
    await _gate(ctx, notice_id, "notice.read")
    _not_yet()


@router.post(
    f"{_N}/response",
    action="notice_response.draft",
    response_model=ResponseOut,
    status_code=201,
    errors=(409, 501),
)
async def response_draft_route(
    notice_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ResponseOut:
    """From the firm's template for (analysis kind, position); provisional before a decision."""
    await _gate(ctx, notice_id, "notice_response.draft")
    _not_yet()


@router.get(f"{_N}/response", action="notice.read", response_model=ResponseOut, errors=(501,))
async def response_route(notice_id: UUID, ctx: Ctx) -> ResponseOut:
    await _gate(ctx, notice_id, "notice.read")
    _not_yet()


@router.put(
    f"{_N}/response",
    action="notice_response.edit",
    response_model=ResponseOut,
    errors=(409, 501),
)
async def response_edit_route(
    notice_id: UUID, body: ResponseEditIn, ctx: Ctx, if_match: IfMatch
) -> ResponseOut:
    """409 `stale_version` (If-Match) or `response_locked` after send."""
    await _gate(ctx, notice_id, "notice_response.edit")
    _not_yet()


@router.post(
    f"{_N}/response/regenerate",
    action="notice_response.edit",
    response_model=ResponseOut,
    errors=(409, 501),
)
async def response_regenerate_route(notice_id: UUID, ctx: Ctx, if_match: IfMatch) -> ResponseOut:
    """Template blocks re-rendered from current figures; human blocks kept."""
    await _gate(ctx, notice_id, "notice_response.edit")
    _not_yet()


@router.post(
    f"{_N}/response/send-for-signature",
    action="notice_response.send_for_signature",
    response_model=SendForSignatureOut,
    status_code=201,
    errors=(409, 501),
)
async def send_for_signature_route(
    notice_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SendForSignatureOut:
    """A C7 draft envelope (`notice_response`) and the payment-confirmation request."""
    await _gate(ctx, notice_id, "notice_response.send_for_signature")
    _not_yet()


@router.post(
    f"{_N}/response/mark-sent",
    action="notice_response.mark_sent",
    response_model=SentOut,
    errors=(409, 501),
)
async def mark_sent_route(
    notice_id: UUID, body: MarkSentIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SentOut:
    """Sent, then Awaiting IRS; 409 `not_ready` with the facts."""
    await _gate(ctx, notice_id, "notice_response.mark_sent")
    _not_yet()


@router.post(
    f"{_N}/agency-replies",
    action="notice.agency_reply",
    response_model=NoticeOut,
    status_code=201,
    errors=(409, 501),
)
async def agency_reply_route(
    notice_id: UUID, body: AgencyReplyIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> NoticeOut:
    await _gate(ctx, notice_id, "notice.agency_reply")
    _not_yet()
