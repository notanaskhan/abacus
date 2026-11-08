"""The notices v1 contract stub (N-04-T02; N-04 §4.3; DEC-2051).
Contract: `docs/contracts/notices.md` (freeze Fri Oct 29, 2027); screens NOT-01, NOT-02, NOT-03;
consumers CLI-05, HOME-01, HOME-02, POR-02 (through the portal's home source, never these routes).

Every IRS and state notice as a `notice` work item: its intake (read by code maps, the agent for
types without a map, or a person), the comparison of the notice, the return as filed and the
information returns, the partner's position (P-04's `notice_position` decision; there is no
notices decide route), the response letter from the firm's template and its send. Every route
answers, in order: a client principal 404 (INV-4: the portal sees only the C7 envelope, the
payment-confirmation request and the POR-02 row, each through its own grant); the matrix action on
the notice's engagement (or the firm for lists and intakes); 501 `not_implemented` until N-04-T06
onward (`notices.workspace` retired at N-04-T27, DEC-2602). Amounts and lines are tax return
information (`tri`); TINs and confirmation numbers are sealed and only their last four digits
travel.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.clock import system_now
from abacus.kernel.errors import NotFound
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    mask_tins_for,
)
from abacus.modules.notices.compute.bracket import FilingStatus
from abacus.modules.organisations.api import MaskedTinOut

JsonRow = dict[str, Any]  # Any: JSON columns as stored

if TYPE_CHECKING:
    from abacus.modules.notices.intake import Intake
    from abacus.modules.notices.service import Notice

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
Tri = classified("restricted", tri=True)
Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2), Tri]
# An amount the notice may not state: the classification sits outside the union (Pydantic drops
# an Annotated member's metadata inside `X | None`).
MaybeMoney = Annotated[Decimal | None, Field(max_digits=18, decimal_places=2), Tri]
Last4 = Annotated[str, Field(pattern=r"^\d{4}$"), classified("confidential")]
# A taxpayer ID on any payload is the masked object (kind, last four), never digits (P-12).
MaskedTin = Annotated[MaskedTinOut | None, classified("restricted", pii_kind="tin")]
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
# C7's `envelope` codes (status-vocabulary.yaml), as the signing provider reports them.
EnvelopeStatus = Literal[
    "draft", "sent", "viewed", "partially_signed", "completed", "declined", "expired", "voided"
]
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
# What a person may edit in intake: every field but the TIN, which is never typed into a
# request (P-12; end-pass S5).
EditableFieldKey = Literal[
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

    tax: MaybeMoney = None
    interest: MaybeMoney = None
    penalty: MaybeMoney = None
    total: MaybeMoney = None
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
    amounts: Annotated[AmountsOut, classified("internal")]
    position: Annotated[Position | None, classified("internal")]  # "· disagreed"
    status: Annotated[NoticeStatus, classified("internal")]
    tile: Annotated[Tile | None, classified("internal")]  # escalated rows have none
    assignee: Annotated[NoticePersonOut | None, classified("internal")]
    authorization: Annotated[AuthorizationOut, classified("internal")]
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
    tin: MaskedTin = None
    confidence: Annotated[
        Decimal | None, Field(ge=0, le=1, decimal_places=3), classified("internal")
    ]
    low_confidence: Annotated[bool, classified("internal")]
    note: Annotated[str | None, classified("internal")] = None  # "date partly obscured"
    helper: Annotated[str | None, classified("internal")] = None  # "Check page 1, top right"
    origin: Annotated[FieldOrigin, classified("internal")]
    confirmed: Annotated[bool, classified("internal")]
    region: Annotated[RegionOut | None, classified("internal")] = None
    citation_id: Annotated[UUID | None, classified("internal")] = None


class MatchCandidateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_entity_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    tin: MaskedTin = None


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
    match: Annotated[MatchOut, classified("internal")]
    authorization: Annotated[AuthorizationOut, classified("internal")]
    duplicate_of: Annotated[UUID | None, classified("internal")] = None  # "Looks like N2"
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    notify_user_ids: Annotated[list[UUID], classified("internal")] = []
    created_work_item_id: Annotated[UUID | None, classified("internal")] = None
    version: Annotated[int, Field(ge=1), classified("internal")]


class NoticeFieldEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[EditableFieldKey, classified("internal")]
    value_text: Annotated[str | None, Field(max_length=200), Tri] = None
    # No plain TIN in a request (P-12; end-pass S5): a misread taxpayer is corrected by picking
    # the client entity (`IntakeUpdateIn.client_entity_id`), whose TIN organisations holds.
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
    # DEC-2953 (US-2.3): why, when past a duplicate: different_notice, different_tax_year,
    # reissued_by_agency or other; 422 `create_anyway_reason_required` without one.
    create_anyway_reason_code: Code | None = None


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

    row: Annotated[NoticeRowOut, classified("internal")]
    notice_date: Annotated[date | None, classified("internal")]
    respond_by_source: Annotated[
        Literal["extracted", "entered", "corrected"] | None, classified("internal")
    ]
    taxpayer_tin: MaskedTin = None
    related_return_id: Annotated[UUID | None, classified("internal")]
    related_return_label: Annotated[str | None, classified("internal")]
    partner_owned: Annotated[bool, classified("internal")]
    signer: Annotated[NoticePersonOut | None, classified("internal")]
    decision_id: Annotated[UUID | None, classified("internal")]
    decided_by: Annotated[NoticePersonOut | None, classified("internal")]
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
    filing_status: Annotated[FilingStatus | None, classified("internal")] = None
    filed_on: Annotated[date | None, classified("internal")] = None
    lines: Annotated[list[CitedLineIn], Field(max_length=200), Tri] = []


class ProposedItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[Literal["line_change", "payer_item"], classified("internal")]
    line_key: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    label: Annotated[str, Field(min_length=1, max_length=200), classified("internal")]
    payer_name: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    info_form: Annotated[str | None, Field(max_length=20), classified("internal")] = None
    amount_shown: MaybeMoney = None
    amount_irs: MaybeMoney = None
    citation_id: Annotated[UUID, classified("internal")]


class ProposedItemsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[ProposedItemIn], Field(min_length=1, max_length=200), Tri]


class AnalysisRowOut(BaseModel):
    """One statement row: notice vs return vs information returns, by code."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    as_filed: MaybeMoney = None
    irs: MaybeMoney = None
    information_returns: MaybeMoney = None
    difference: MaybeMoney = None
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
    bracket_check: Annotated[BracketCheckOut | None, classified("internal")]
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
    checks: Annotated[AnalysisChecksOut | None, classified("internal")]
    sources: Annotated[list[NoticeSourceOut], classified("internal")]
    agent: Annotated[AgentBlockOut, classified("internal")]
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
    author: Annotated[NoticePersonOut, classified("internal")]
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

    amounts: Annotated[AmountsOut, classified("internal")]
    method_label: Annotated[PaymentMethod | None, classified("internal")]
    paid_on: Annotated[date | None, classified("internal")]
    confirmation_request_item_id: Annotated[UUID | None, classified("internal")]
    request_state: Annotated[str | None, classified("internal")]


def _payment_out(raw: object) -> PaymentOut | None:
    """NOT-03's Payment band from the response's settings. A label, never an instrument."""
    if not isinstance(raw, dict):
        return None
    payment = cast(dict[str, Any], raw)  # Any: JSON from the database
    if not payment.get("required"):
        return None
    item = payment.get("confirmation_request_item_id")
    return PaymentOut(
        amounts=AmountsOut(total=payment.get("amount")),
        method_label=payment.get("method_label"),
        paid_on=payment.get("paid_on"),
        confirmation_request_item_id=UUID(str(item)) if item else None,
        request_state=("accepted" if payment.get("confirmation_accepted") else "requested")
        if item
        else None,
    )


class ApprovalStepOut(BaseModel):
    """P-04's ladder: Prepared KO ✓ · Reviewed SI in progress · Approved DR ring."""

    model_config = ConfigDict(frozen=True)

    level: Annotated[str, classified("internal")]
    person: Annotated[NoticePersonOut | None, classified("internal")]
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
    payment: Annotated[PaymentOut | None, classified("internal")]
    signer_contact_ids: Annotated[list[UUID], classified("internal")]
    channel: Annotated[Channel | None, classified("internal")]
    follow_up_days: Annotated[int, Field(ge=1, le=365), classified("internal")]
    owner: Annotated[NoticePersonOut | None, classified("internal")]
    approvals: Annotated[list[ApprovalStepOut], classified("internal")]
    readiness: Annotated[Readiness, classified("internal")]
    readiness_facts: Annotated[list[ReadinessFactOut], classified("internal")]
    envelope_id: Annotated[UUID | None, classified("internal")]
    envelope_status: Annotated[EnvelopeStatus | None, classified("internal")]  # C7 `envelope`
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
    confirmation_last4: Annotated[
        str | None, Field(pattern=r"^\d{4}$"), classified("confidential")
    ] = None


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


async def _gate_firm(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("notices")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


async def _gate(ctx: AuthContext, notice_id: UUID, action: str) -> None:
    if ctx.client:
        raise NotFound("notices")
    engagement_id = await work_item_engagement(ctx.tenant, notice_id)
    if engagement_id is None:
        raise NotFound("notice")
    ref = await get_ref(ctx, engagement_id)
    # A notice is its work item: scope the check to it so `function_in` (preparer, reviewers,
    # signer) is evaluated on the person's assignment, not refused for want of one.
    await authorise(ctx, action, replace(ref.resource(), work_item_id=notice_id))


# A stub whose response carries a TIN (`MaskedTinOut`) already returns through the central mask
# (`mask_tins_for`; TASK-1207 item 6), so the implementation that replaces `_not_yet()` keeps it.


_OWN_ACTIONS: tuple[str, ...] = (
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
)


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper() or "?"


async def _rows_out(ctx: AuthContext, rows: list[Notice], on: date) -> list[NoticeRowOut]:
    from abacus.kernel.db import tenant_session
    from abacus.modules.notices import service
    from abacus.modules.organisations.api import client_names

    entities = [n.client_entity_id for n in rows if n.client_entity_id is not None]
    async with tenant_session(ctx.tenant) as session:
        clients = await client_names(session, entities) if entities else {}
    people = await service.names([n.assignee_user_id for n in rows])
    out: list[NoticeRowOut] = []
    for n in rows:
        named = clients.get(n.client_entity_id) if n.client_entity_id else None
        assignee = None
        if n.assignee_user_id is not None and n.assignee_user_id in people:
            who = people[n.assignee_user_id]
            assignee = NoticePersonOut(
                user_id=n.assignee_user_id, name=who, initials=_initials(who)
            )
        out.append(
            NoticeRowOut(
                id=n.id,
                engagement_id=n.engagement_id,
                client_entity_id=n.client_entity_id or n.engagement_id,
                client_name=named.client_entity_name if named else "",
                form_line=f"Form {n.form}" if n.form else None,
                agency=cast(Agency, n.agency or "irs"),
                agency_name=n.agency_name or ("IRS" if n.agency != "state" else "State"),
                notice_type_key=cast(NoticeTypeKey, n.notice_type_key or "unknown"),
                notice_code=n.notice_code,
                title=n.title or n.notice_code,
                tax_year=n.tax_year or on.year - 1,
                received_on=n.received_on,
                respond_by=n.respond_by,
                respond_by_days=None if n.respond_by is None else (n.respond_by - on).days,
                risk=cast(RiskBand, service.risk_band(n.respond_by, on, n.status)),
                sent_on=None,
                amounts=AmountsOut(
                    tax=n.amount_tax,
                    interest=n.amount_interest,
                    penalty=n.amount_penalty,
                    total=n.amount_total,
                    interest_to=n.interest_to,
                ),
                position=cast(Position | None, n.position),
                status=cast(NoticeStatus, n.status),
                tile=cast(Tile | None, n.tile),
                assignee=assignee,
                authorization=AuthorizationOut(
                    kind=cast(AuthorizationKind, n.authorization_kind),
                    label=n.authorization_label,
                    on_file=n.authorization_kind != "none",
                    can_represent=n.can_represent,
                    authorization_id=n.authorization_id,
                ),
                version=n.row_version,
            )
        )
    return out


async def _notice_out(ctx: AuthContext, n: Notice) -> NoticeOut:
    from abacus.modules.identity.api import allowed_actions
    from abacus.modules.notices import service

    on = await service.on_day(ctx)
    row = (await _rows_out(ctx, [n], on))[0]
    ref = await get_ref(ctx, n.engagement_id)
    can = await allowed_actions(ctx, ref.resource(), _OWN_ACTIONS)
    if n.status != "received":
        can = [a for a in can if a != "notice.start"]
    return NoticeOut(
        row=row,
        notice_date=n.notice_date,
        respond_by_source=cast(
            Literal["extracted", "entered", "corrected"] | None, n.respond_by_source
        ),
        taxpayer_tin=None,  # the sealed TIN and its mask arrive with the intake (N-04-T07)
        related_return_id=n.related_return_id,
        related_return_label=None,
        partner_owned=n.partner_owned,
        signer=None,
        decision_id=n.decision_id,
        decided_by=None,
        decided_at=n.decided_at,
        follow_up_on=n.follow_up_on,
        closed_on=n.closed_on,
        escalated_reason=n.escalated_reason,
        client_visible=n.client_visible,
        readiness=[
            ReadinessFactOut(key="decision", met=n.position is not None, label="Partner decision"),
        ],
        allowed_actions=[cast(NoticeAction, a) for a in _OWN_ACTIONS if a in can],
    )


# The reason an intake opened for manual entry, in words (N-04 US-2.2): never guessed.
_MANUAL_REASON: Final[dict[str, str]] = {
    "no_map": "We don't have a map for this notice — enter the fields",
    "no_file": "There's no file to read yet — enter the fields",
    "kill_switch": "Reading is switched off for now — enter the fields",
    "flag_off": "Read automatically isn't on",
    "provider_terms": "The reading service isn't cleared for this firm — enter the fields",
    "terms_not_covering": "The reading service isn't cleared for this firm — enter the fields",
    "boundary_basis": "This taxpayer's file can't go to the reading service — enter the fields",
    "consent_7216": "No §7216 consent covers this taxpayer — enter the fields",
    "consent_missing": "No §7216 consent covers this taxpayer — enter the fields",
    "daily_page_cap": "Today's reading limit is reached — enter the fields",
    "size_limit": "This file is too large to read — enter the fields",
    "provider_error": "Couldn't read this file — enter the fields",
}
_FAILED_REASON: Final = "Couldn't read this file — enter the fields"


async def _match_out(ctx: AuthContext, found: Intake) -> MatchOut:
    """Code's match or the person's pick. Names and the return's label are read here, for a person
    already allowed the intake, so none is stored on it."""
    from abacus.modules.organisations.api import entity_display_name
    from abacus.modules.tax.api import return_label

    match = found.match
    entity = _uuid_of(match.get("client_entity_id"))
    return_id = _uuid_of(match.get("return_id"))
    ids = [UUID(str(c)) for c in cast("list[object]", match.get("candidates") or [])]
    candidates = [
        MatchCandidateOut(client_entity_id=c, name=await entity_display_name(ctx.tenant, c) or "")
        for c in ids
    ]
    return MatchOut(
        client_entity_id=entity,
        client_name=None if entity is None else await entity_display_name(ctx.tenant, entity),
        method=cast(
            Literal["name_tin", "tin", "name", "manual"] | None, match.get("method") or None
        ),
        candidates=candidates,
        return_id=return_id,
        return_label=None if return_id is None else await return_label(ctx.tenant, return_id),
        office=None,
    )


def _uuid_of(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _manual_reason(found: Intake) -> str | None:
    if found.status == "failed":
        return _FAILED_REASON
    if found.status != "manual_entry":
        return None
    return _MANUAL_REASON.get(
        str(found.match.get("manual_reason_code")), _MANUAL_REASON["flag_off"]
    )


async def _intake_read(ctx: AuthContext, found: Intake) -> IntakeOut:
    return _intake_out(found, await _match_out(ctx, found))


_NO_MATCH: Final = MatchOut(
    client_entity_id=None,
    client_name=None,
    method=None,
    candidates=[],
    return_id=None,
    return_label=None,
    office=None,
)


def _intake_out(found: Intake, match: MatchOut = _NO_MATCH) -> IntakeOut:
    """The sheet's read; a TIN travels as its last four only."""
    auth = found.authorization
    kind = cast(AuthorizationKind, auth.get("kind", "none"))
    return IntakeOut(
        id=found.id,
        status=cast(IntakeStatus, found.status),
        source=cast(IntakeSource, found.source),
        file_name=None,
        pages=None,
        uploaded_by_label=None,
        extraction_mode=cast(ExtractionMode | None, found.extraction_mode),
        manual_reason=_manual_reason(found),
        fields=[
            IntakeFieldOut(
                key=cast(FieldKey, f.key),
                value_text=None if f.key == "taxpayer.tin" else f.value_text,
                confidence=f.confidence,
                low_confidence=f.low_confidence and not f.confirmed,
                origin=cast(FieldOrigin, f.origin),
                confirmed=f.confirmed,
                citation_id=f.citation_id,
            )
            for f in found.fields
        ],
        match=match,
        authorization=AuthorizationOut(
            kind=kind,
            label=str(auth.get("label", "None · blocked")),
            on_file=kind != "none",
            can_represent=kind in ("form_2848", "state_poa"),
        ),
        duplicate_of=found.duplicate_of,
        assignee_user_id=found.assignee_user_id,
        notify_user_ids=list(found.notify_user_ids),
        created_work_item_id=found.created_work_item_id,
        version=found.row_version,
    )


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
    from abacus.modules.notices import service

    on = await service.on_day(ctx)
    rows = await service.visible_notices(ctx)
    counts = service.tallies(rows, on)
    shown = [
        n
        for n in rows
        if (agency is None or n.agency == agency)
        and (type is None or n.notice_type_key == type)
        and (assignee is None or n.assignee_user_id == assignee)
        and (status is None or n.status == status)
        and (tile is None or n.tile == tile)
        and (client_entity_id is None or n.client_entity_id == client_entity_id)
        and (
            respond_by is None
            or (n.respond_by is not None and n.open and (n.respond_by - on).days <= respond_by)
        )
    ]
    items = await _rows_out(ctx, shown, on)
    if q:
        needle = q.casefold()
        items = [
            r
            for r in items
            if needle in r.client_name.casefold() or needle in r.notice_code.casefold()
        ]
    return ListPage[NoticeRowOut](items=items, total=len(items), counts=counts.tiles)


@router.get(
    "/notices/summary", action="notice.read", response_model=NoticesSummaryOut, errors=(501,)
)
async def notices_summary_route(ctx: Ctx) -> NoticesSummaryOut:
    await _gate_firm(ctx, "notice.read")
    from abacus.modules.notices import service

    counts = service.tallies(await service.visible_notices(ctx), await service.on_day(ctx))
    labels = {"cp2000": "CP2000", "cp14": "CP14", "cp501": "CP501", "cp503": "CP503"}
    labels |= {"cp504": "CP504", "cp3219a": "CP3219A", "state": "State", "unknown": "Other"}
    return NoticesSummaryOut(
        tiles=cast(dict[Tile, int], counts.tiles),
        by_type=[
            TypeCountOut(key=k, label=labels.get(k, k.upper()), count=v)
            for k, v in sorted(counts.by_type.items())
        ],
        open=counts.open,
        due_within_7=counts.due_within_7,
        blocked=counts.blocked,
        agent_stage="off",  # notices.responder stays off until a mode is cleared (N-04 §6)
    )


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
    """An intake from a stored file; the sheet polls while `extracting` (N-04-T07)."""
    await _gate_firm(ctx, "notice_intake.create")
    from abacus.modules.notices import intake

    found = await intake.create(
        ctx,
        source=body.source,
        evidence_version_id=body.evidence_version_id,
        inbox_item_id=body.inbox_item_id,
    )
    return await mask_tins_for(ctx, (await _intake_read(ctx, found)))


@router.get(_I, action="notice_intake.read", response_model=IntakeOut, errors=(501,))
async def intake_route(intake_id: UUID, ctx: Ctx) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.read")
    from abacus.modules.notices import intake

    return await mask_tins_for(ctx, await _intake_read(ctx, await intake.intake(ctx, intake_id)))


@router.put(_I, action="notice_intake.update", response_model=IntakeOut, errors=(409, 501))
async def intake_update_route(
    intake_id: UUID, body: IntakeUpdateIn, ctx: Ctx, if_match: IfMatch
) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.update")
    from abacus.modules.notices import intake

    found = await intake.revise(
        ctx,
        intake_id,
        if_match,
        fields=[(f.key, f.value_text, f.confirm) for f in body.fields],
        client_entity_id=body.client_entity_id,
        related_return_id=body.related_return_id,
        assignee_user_id=body.assignee_user_id,
        notify_user_ids=body.notify_user_ids,
    )
    return await mask_tins_for(ctx, (await _intake_read(ctx, found)))


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
    """409 `low_confidence_unconfirmed`, `duplicate_unresolved`, `no_notice_engagement`; 422
    `create_anyway_reason_required`."""
    await _gate_firm(ctx, "notice_intake.confirm")
    from abacus.modules.notices import intake

    notice_id, engagement_id = await intake.create_notice(
        ctx,
        intake_id,
        client_entity_id=body.client_entity_id,
        assignee_id=body.assignee_id,
        engagement_id=body.engagement_id,
        related_return_id=body.related_return_id,
        create_anyway=body.create_anyway,
        notify_user_ids=body.notify_user_ids,
        create_anyway_reason=body.create_anyway_reason_code,
    )
    return CreatedNoticeOut(notice_id=notice_id, engagement_id=engagement_id)


@router.post(
    f"{_I}/attach", action="notice_intake.confirm", response_model=IntakeOut, errors=(409, 501)
)
async def intake_attach_route(
    intake_id: UUID, body: IntakeAttachIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.confirm")
    from abacus.modules.notices import intake

    found = await intake.attach(ctx, intake_id, body.notice_id)
    return await mask_tins_for(ctx, await _intake_read(ctx, found))


@router.post(
    f"{_I}/discard", action="notice_intake.confirm", response_model=IntakeOut, errors=(409, 501)
)
async def intake_discard_route(
    intake_id: UUID, body: IntakeDiscardIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeOut:
    await _gate_firm(ctx, "notice_intake.confirm")
    from abacus.modules.notices import intake

    found = await intake.discard(ctx, intake_id, body.reason_code)
    return await mask_tins_for(ctx, await _intake_read(ctx, found))


@router.get(_N, action="notice.read", response_model=NoticeOut, errors=(501,))
async def notice_route(notice_id: UUID, ctx: Ctx) -> NoticeOut:
    await _gate(ctx, notice_id, "notice.read")
    from abacus.modules.notices import service

    return await mask_tins_for(ctx, await _notice_out(ctx, await service.notice(ctx, notice_id)))


@router.patch(_N, action="notice.update", response_model=NoticeOut, errors=(409, 501))
async def notice_patch_route(
    notice_id: UUID, body: NoticePatchIn, ctx: Ctx, if_match: IfMatch
) -> NoticeOut:
    """`notice.assign` for `assignee_id` alone, `notice.update` otherwise (the service checks)."""
    await _gate(ctx, notice_id, "notice.assign" if _assign_only(body) else "notice.update")
    from abacus.modules.notices import service

    found = await service.edit(
        ctx,
        notice_id,
        if_match,
        assignee_id=body.assignee_id,
        respond_by=body.respond_by,
        related_return_id=body.related_return_id,
        client_visible=body.client_visible,
    )
    return await mask_tins_for(ctx, await _notice_out(ctx, found))


def _assign_only(body: NoticePatchIn) -> bool:
    return body.model_fields_set == {"assignee_id"}


@router.post(f"{_N}:start", action="notice.start", response_model=NoticeOut, errors=(409, 501))
async def notice_start_route(
    notice_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> NoticeOut:
    """received to classified (the analysis starts with N-04-T11)."""
    await _gate(ctx, notice_id, "notice.start")
    from abacus.modules.notices import service

    found = await service.start(ctx, notice_id, None)
    return await mask_tins_for(ctx, await _notice_out(ctx, found))


@router.put(
    f"{_N}/return-as-filed",
    action="notice.record_as_filed",
    response_model=AnalysisRunOut,
    errors=(409, 501),
)
async def return_as_filed_route(
    notice_id: UUID, body: ReturnAsFiledIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AnalysisRunOut:
    """A person's return-as-filed snapshot, every line cited; then code re-runs (N-04-T11)."""
    await _gate(ctx, notice_id, "notice.record_as_filed")
    from abacus.modules.notices import analysis

    await analysis.record_return_as_filed(
        ctx,
        notice_id,
        source=body.source,
        filing_status=body.filing_status,
        filed_on=body.filed_on,
        lines=[(line.key, line.label, line.value, line.citation_id) for line in body.lines],
    )
    return await _run_out(ctx, notice_id)


@router.put(
    f"{_N}/proposed-items",
    action="notice.record_as_filed",
    response_model=AnalysisRunOut,
    errors=(409, 501),
)
async def proposed_items_route(
    notice_id: UUID, body: ProposedItemsIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AnalysisRunOut:
    """A person's cited entry of the notice's proposed items; then code re-runs (N-04-T11)."""
    await _gate(ctx, notice_id, "notice.record_as_filed")
    from abacus.modules.notices import analysis

    await analysis.record_proposed_items(ctx, notice_id, [i.model_dump() for i in body.items])
    return await _run_out(ctx, notice_id)


async def _run_out(ctx: AuthContext, notice_id: UUID) -> AnalysisRunOut:
    from abacus.modules.notices import analysis

    version, status, reused = await analysis.start(ctx, notice_id)
    return AnalysisRunOut(version=version, status=cast(AnalysisStatus, status), reused=reused)


@router.get(f"{_N}/analysis", action="notice.read", response_model=AnalysisOut, errors=(501,))
async def analysis_route(notice_id: UUID, ctx: Ctx) -> AnalysisOut:
    """The newest analysis version as code recorded it (NOT-02 b, c, d)."""
    await _gate(ctx, notice_id, "notice.read")
    from abacus.modules.notices import analysis

    row = await analysis.latest(ctx, notice_id)
    if row is None:
        raise NotFound("notice_analysis")
    checks = cast(
        JsonRow,
        row["checks"] or {},
    )
    bracket_check = cast(
        JsonRow | None,
        checks.get("bracket_check"),
    )
    out = AnalysisOut(
        version=row["version"],
        status=row["status"],
        analysis_kind=row["analysis_kind"],
        progress_label=None,
        rows=[AnalysisRowOut(**r) for r in row["rows"]],
        information_returns=[InformationReturnOut(**r) for r in row["information_returns"]],
        transcript_rows=[
            AnalysisRowOut(**r) for r in cast(list[JsonRow], checks.get("transcript_rows") or [])
        ],
        checks=AnalysisChecksOut(
            difference_explained=bool(checks.get("difference_explained")),
            total_foots=bool(checks.get("total_foots", True)),
            bracket_check=None
            if not bracket_check or bracket_check.get("rate") is None
            else BracketCheckOut(
                rate=Decimal(bracket_check["rate"]),
                expected=Decimal(bracket_check["expected"]),
                notice=Decimal(bracket_check["notice"]),
                agrees=bool(bracket_check["agrees"]),
                reason=bracket_check.get("reason"),
            ),
        ),
        sources=[],
        agent=AgentBlockOut(
            stage=row["agent_stage"],
            run_id=row["agent_run_id"],
            explanation=None,
            recommended_position=row["recommended_position"],
            refusal=None,
            citation_ids=[],
        ),
        decision_card_id=None,
        engine_name=row["engine_name"],
        engine_version=row["engine_version"],
        inputs_hash=row["inputs_hash"],
    )
    return await mask_tins_for(ctx, out)


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
    """Starts `NoticeAnalysisWorkflow`; NOT-02 polls the analysis. Idempotent on `inputs_hash`."""
    await _gate(ctx, notice_id, "notice.analyze")
    return await _run_out(ctx, notice_id)


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
    from abacus.modules.notices import analysis

    card_id = await analysis.request_decision(ctx, notice_id, body.note)
    return DecisionRequestOut(decision_card_id=card_id)


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
    from abacus.modules.notices import analysis, service

    note_id = await analysis.add_note(ctx, notice_id, body.body, body.decision_card_id)
    name = (await service.names([ctx.user_id])).get(ctx.user_id, "")
    initials = "".join(p[0] for p in name.split()[:2]).upper() or "?"
    return NoticeNoteOut(
        id=note_id,
        author=NoticePersonOut(user_id=ctx.user_id, name=name, initials=initials),
        created_at=system_now(),
    )


@router.get(
    f"{_N}/activity",
    action="notice.read",
    response_model=ListPage[ActivityItemOut],
    errors=(501,),
)
async def notice_activity_route(
    notice_id: UUID, ctx: Ctx, cursor: str | None = None
) -> ListPage[ActivityItemOut]:
    await _gate(ctx, notice_id, "notice.read")
    from abacus.modules.notices import service

    items = [
        ActivityItemOut(
            at=at,
            event=action,
            label=action.replace("_", " ").replace(".", " · "),
            actor_label=None if kind == "human" else "System",
        )
        for at, action, kind in await service.audit_events(ctx, notice_id)
    ]
    return ListPage[ActivityItemOut](items=items, total=len(items))


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
    from abacus.modules.notices import response

    return await _response_out(ctx, await response.draft(ctx, notice_id))


async def _response_out(ctx: AuthContext, found: object) -> ResponseOut:
    """NOT-03's response as stored (N-04-T12): blocks with provenance, settings, readiness."""
    from abacus.modules.notices import response, service

    r = cast(response.Response, found)
    n = await service.notice(ctx, r.notice_id)
    code = response.blocked_code(
        n.position, response.drafted_for(n.position, r.position_source), r.blocks
    )
    settings = r.settings
    return ResponseOut(
        id=r.id,
        version_no=r.version_no,
        content_hash=r.content_hash,
        template_key=r.template_key,
        position=cast(Any, n.position),  # Any: the notices CHECK holds the words
        position_source=cast(Any, r.position_source),  # Any: 0650's CHECK
        position_mismatch=code == "position_mismatch",
        blocks=[
            BlockOut(
                key=b.key,
                origin=cast(Any, b.origin),  # Any: template or human
                template_block_key=b.template_block_key,
                text=b.text,
                edited=b.edited,
                citation_ids=[],
            )
            for b in r.blocks
        ],
        enclosures=[],
        payment=_payment_out(settings.get("payment")),
        signer_contact_ids=list(settings.get("signer_contact_ids") or []),
        channel=settings.get("channel"),
        follow_up_days=int(settings.get("follow_up_days") or 60),
        owner=None,
        approvals=[],
        readiness="waiting_decision" if code == "decision_pending" else "in_review",
        readiness_facts=[
            ReadinessFactOut(key="decision", met=n.position is not None, label="Position decided")
        ],
        envelope_id=None,
        envelope_status=None,
        locked=r.locked,
        row_version=r.row_version,
    )


@router.get(f"{_N}/response", action="notice.read", response_model=ResponseOut, errors=(501,))
async def response_route(notice_id: UUID, ctx: Ctx) -> ResponseOut:
    await _gate(ctx, notice_id, "notice.read")
    from abacus.modules.notices import response

    return await _response_out(ctx, await response.response(ctx, notice_id))


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
    from abacus.modules.notices import response

    found = await response.edit(
        ctx,
        notice_id,
        if_match,
        blocks=[(b.key, b.text) for b in body.blocks],
        settings={
            "signer_contact_ids": body.signer_contact_ids,
            "channel": body.channel,
            "follow_up_days": body.follow_up_days,
            "owner_user_id": body.owner_user_id,
        },
    )
    return await _response_out(ctx, found)


@router.post(
    f"{_N}/response/regenerate",
    action="notice_response.edit",
    response_model=ResponseOut,
    errors=(409, 501),
)
async def response_regenerate_route(notice_id: UUID, ctx: Ctx, if_match: IfMatch) -> ResponseOut:
    """Template blocks re-rendered from current figures; human blocks kept."""
    await _gate(ctx, notice_id, "notice_response.edit")
    from abacus.modules.notices import response

    return await _response_out(ctx, await response.regenerate(ctx, notice_id, if_match))


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
    """A C7 draft envelope (`notice_response`); SIG-02 d opens it (A-04 N-04-T16)."""
    await _gate(ctx, notice_id, "notice_response.send_for_signature")
    from abacus.modules.notices import sending

    envelope_id = await sending.send_for_signature(ctx, notice_id)
    return SendForSignatureOut(
        envelope_id=envelope_id,
        confirmation_request_item_id=await sending.confirmation_item_of(ctx, notice_id),
    )


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
    from abacus.modules.notices import sending

    sent_on, follow_up, last4 = await sending.mark_sent(
        ctx,
        notice_id,
        channel=body.channel,
        confirmation_no=body.confirmation_no,
        sent_on=body.sent_on,
        follow_up_days=body.follow_up_days,
    )
    return SentOut(sent_on=sent_on, follow_up_on=follow_up, confirmation_last4=last4)


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
    from abacus.modules.notices import sending, service

    await sending.agency_reply(
        ctx,
        notice_id,
        outcome=body.outcome,
        closed_on=body.closed_on,
        note=body.note,
        evidence_version_id=body.evidence_version_id,
    )
    return await mask_tins_for(ctx, await _notice_out(ctx, await service.notice(ctx, notice_id)))
