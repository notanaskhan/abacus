"""The A-07 contract stub, part 2: AUD-21 to AUD-25 (A-07-T05; SPEC-644; DEC-2231).
Contract: `docs/contracts/audit-completion.md` (representation letter, governance
communications, report builder, issuance and release, filings, assembly and archive).

Every route is under `/v1/audits/{work_item_id}` with one matrix action and answers, in order: a
client principal 404 (INV-4); 404 for a work item that is not an assurance work item; the action
on the work item's engagement with the work item in the resource; then 501 `not_implemented`
until its task (A-07-T24, T26, T27, T30, T31, T36, T37, T42) and the Jan 27, 2028 flags
`audits.letters`, `audits.report_release` and `audits.archive` (A-07-T33).

Human-only with fresh MFA (five layers, chapter 03 §4.7): `rep_letter.approve`,
`governance_comm.approve_send`, `report.release`, `archive.lock`, `archive_addition.approve`.
Letters and the report are composed from firm template rows (database content, P-25 off): no
model prose and no materiality amount reaches client text. Release takes no hold and no Undo
(DEC-2260). After lock, only `archive_addition.*`, `archive.read` and `archive.verify` act on the
work item (`archived_exempt`, A-07-T14).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = Annotated[str, classified("internal")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
Gate = Literal["G5", "G6", "G7", "G8", "G9"]
LetterAction = Literal[
    "rep_letter.draft", "rep_letter.request_approval", "rep_letter.approve", "rep_letter.send",
    "envelope.remind", "governance_comm.draft", "governance_comm.request_approval",
    "governance_comm.approve_send", "governance_comm.manage_recipients",
]  # fmt: skip
ReportAction = Literal[
    "report.draft", "report.request_decision", "report.generate", "report.release",
    "filing.update", "sign_off.l4",
]  # fmt: skip
ArchiveAction = Literal[
    "archive.build_index", "archive.request_lock", "archive.lock", "archive.verify",
    "archive_addition.create", "archive_addition.approve",
]  # fmt: skip
GovernanceKind = Literal[
    "planning_260", "completion_260", "sd_mw_265", "reportable_703", "management_letter"
]
AdditionReason = Literal[
    "au_c_585_omitted_procedure", "au_c_560_subsequently_discovered_fact", "other"
]


class ReleaseRunAcceptedOut(BaseModel):
    """202: a run started (compose, render, release, binder index, lock, verify)."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    status_url: Internal


class CitationChipOut(BaseModel):
    """A reason or citation chip on a paragraph (C4)."""

    model_config = ConfigDict(frozen=True)

    citation_id: Annotated[UUID, classified("internal")]
    label: Internal


# --- representation letter (AUD-21) --------------------------------------------------------------


class LetterRepresentationOut(BaseModel):
    """One toggle in the structure pane (DV-5: general 1-11 locked, specific 12-15 by trigger)."""

    model_config = ConfigDict(frozen=True)

    key: Internal
    kind: Annotated[Literal["general", "specific"], classified("internal")]
    paragraph_no: Annotated[int | None, Field(ge=1), classified("internal")]
    title: Internal  # the firm template's wording
    locked: Annotated[bool, classified("internal")]  # "Always included"
    included: Annotated[bool, classified("internal")]
    trigger_ref: Annotated[str | None, classified("internal")]  # the finding or SUM that triggers
    firm_editable: Annotated[bool, classified("internal")]
    citations: Annotated[list[CitationChipOut], classified("internal")]


class LetterParagraphOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Internal
    number: Annotated[int | None, Field(ge=1), classified("internal")]
    text: Annotated[str, classified("confidential")]
    human_edited: Annotated[bool, classified("internal")]
    citations: Annotated[list[CitationChipOut], classified("internal")]


class RepresentationLetterVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    content_hash: Sha256
    created_by_name: Internal  # "<person> via Agent" for a composed draft (INV-5)
    created_at: Annotated[datetime, classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]
    sum_snapshot_id: Annotated[UUID | None, classified("internal")]
    generated_document_id: Annotated[UUID | None, classified("internal")]


class RepLetterSignerOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    order: Annotated[int, Field(ge=1), classified("internal")]
    identity: Annotated[Literal["email_code"], classified("internal")]  # DF-11, DV-1
    viewed_at: Annotated[datetime | None, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]


class RepresentationLetterOut(BaseModel):
    """GET …/representation-letter: structure, paper model, signers and the G7 check."""

    model_config = ConfigDict(frozen=True)

    status: Annotated[
        Literal[
            "drafting", "draft", "awaiting_partner_approval", "approved", "sent", "signed",
            "date_mismatch",
        ],
        classified("internal"),
    ]  # fmt: skip
    current_version: Annotated[RepresentationLetterVersionOut | None, classified("internal")]
    representations: Annotated[list[LetterRepresentationOut], classified("internal")]
    paragraphs: Annotated[list[LetterParagraphOut], classified("internal")]
    signers: Annotated[list[RepLetterSignerOut], classified("internal")]
    report_date: Annotated[date | None, classified("internal")]
    dated_as_of: Annotated[date | None, classified("internal")]  # always the report date
    signed_on: Annotated[date | None, classified("internal")]
    g7_met: Annotated[bool, classified("internal")]
    envelope_id: Annotated[UUID | None, classified("internal")]
    watermark: Annotated[Literal["draft", "none"], classified("internal")]
    allowed_actions: Annotated[list[LetterAction], classified("internal")]
    version: Annotated[int, classified("internal")]


class RepresentationToggleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    included: Annotated[bool, classified("internal")]
    seen_version: Annotated[int, classified("internal")]


class LetterParagraphIn(BaseModel):
    """An edit on a firm-editable paragraph only (409 `paragraph_locked` otherwise)."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=8000), classified("confidential")]
    seen_version: Annotated[int, classified("internal")]


class LetterApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seen_hash: Sha256


class LetterSendIn(BaseModel):
    """C7 envelope with `date_as_of` = the report date (never typed)."""

    model_config = ConfigDict(extra="forbid")

    signer_contact_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=5), classified("internal")
    ]
    seen_version: Annotated[int, classified("internal")]


# --- governance communications (AUD-22) ----------------------------------------------------------


class GovernanceRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[GovernanceKind, classified("internal")]
    standard: Internal  # "AU-C 260", "AU-C 265 · 703"
    status: Annotated[
        Literal["not_started", "draft", "awaiting_ep_approval", "sent", "acknowledged"],
        classified("internal"),
    ]
    overdue: Annotated[bool, classified("internal")]  # derived from due_on; never stored
    due_on: Annotated[date | None, classified("internal")]
    sent_at: Annotated[datetime | None, classified("internal")]
    acknowledged_at: Annotated[datetime | None, classified("internal")]
    acknowledged_by_body: Annotated[str | None, classified("confidential")]
    channel: Annotated[Literal["governance_room", "ack_envelope"] | None, classified("internal")]


class GovernanceListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[GovernanceRowOut], classified("internal")]
    required_sent: Annotated[
        int, Field(ge=0), classified("internal")
    ]  # DV-6 "2 of 3 required sent"
    required_total: Annotated[int, Field(ge=0), classified("internal")]
    allowed_actions: Annotated[list[LetterAction], classified("internal")]


class GovernanceSectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Internal
    title: Internal
    text: Annotated[str, classified("confidential")]
    built_from: Annotated[list[str], classified("internal")]  # source refs: risks, findings, SOC
    human_edited: Annotated[bool, classified("internal")]
    citations: Annotated[list[CitationChipOut], classified("internal")]


class GovernanceCommunicationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    row: Annotated[GovernanceRowOut, classified("internal")]
    version_no: Annotated[int | None, Field(ge=1), classified("internal")]
    content_hash: Annotated[str | None, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    sections: Annotated[list[GovernanceSectionOut], classified("internal")]
    watermark: Annotated[Literal["draft", "none"], classified("internal")]
    allowed_actions: Annotated[list[LetterAction], classified("internal")]
    version: Annotated[int, classified("internal")]


class GovernanceCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[GovernanceKind, classified("internal")]


class GovernanceSectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=8000), classified("confidential")]
    seen_version: Annotated[int, classified("internal")]


class GovernanceSendIn(BaseModel):
    """EP approve-and-send to the POR-15 governance room, or a SIG-02 acknowledgement envelope."""

    model_config = ConfigDict(extra="forbid")

    governance_body_id: Annotated[UUID, classified("internal")]
    recipient_contact_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=20), classified("internal")
    ]
    channel: Annotated[Literal["governance_room", "ack_envelope"], classified("internal")]
    seen_hash: Sha256


class GovernanceRecipientOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    governance_body_id: Annotated[UUID, classified("internal")]
    body_name: Annotated[str, classified("confidential")]
    member_count: Annotated[int, Field(ge=0), classified("internal")]
    ack_required: Annotated[bool, classified("internal")]


class GovernanceRecipientsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[GovernanceRecipientOut], classified("internal")]
    version: Annotated[int, classified("internal")]


class GovernanceRecipientsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    governance_body_ids: Annotated[list[UUID], Field(max_length=5), classified("internal")]
    seen_version: Annotated[int, classified("internal")]


# --- report builder (AUD-23) ---------------------------------------------------------------------


class ReportChoiceOut(BaseModel):
    """One structured choice (opinion form, modification, toggles); never free text."""

    model_config = ConfigDict(frozen=True)

    field: Internal
    value: Annotated[str | bool | None, classified("internal")]
    locked_by: Annotated[str | None, classified("internal")]  # e.g. "AUD-19 going concern"
    decision_card_id: Annotated[UUID | None, classified("internal")]  # opinion: the EP's card
    reason_code: Annotated[str | None, classified("internal")]


class ReportParagraphOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    block_id: Internal
    heading: Annotated[str | None, classified("internal")]
    text: Annotated[str, classified("confidential")]
    included: Annotated[bool, classified("internal")]
    reason_code: Annotated[str | None, classified("internal")]
    citations: Annotated[list[CitationChipOut], classified("internal")]


class ReportVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    content_hash: Sha256
    report_date: Annotated[date | None, classified("internal")]
    city: Annotated[str | None, classified("internal")]
    created_by_name: Internal
    created_at: Annotated[datetime, classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]  # the EP's L4 sign-off
    approved_at: Annotated[datetime | None, classified("internal")]


class GeneratedReportDocumentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_document_id: Annotated[UUID, classified("internal")]
    format: Annotated[Literal["docx", "pdf"], classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    watermark: Annotated[Literal["draft", "none"], classified("internal")]
    out_of_date: Annotated[bool, classified("internal")]  # AUD-23 j (R2)


class AuditReportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_kind: Annotated[Literal["audit", "review", "compilation"], classified("internal")]
    framework: Internal
    status: Annotated[Literal["draft", "approved", "released", "reissued"], classified("internal")]
    current_version: Annotated[ReportVersionOut | None, classified("internal")]
    choices: Annotated[list[ReportChoiceOut], classified("internal")]
    paragraphs: Annotated[list[ReportParagraphOut], classified("internal")]
    documents: Annotated[list[GeneratedReportDocumentOut], classified("internal")]
    eqr_required_not_concurred: Annotated[bool, classified("internal")]  # DV-4 "Request EQR…"
    allowed_actions: Annotated[list[ReportAction], classified("internal")]
    version: Annotated[int, classified("internal")]


class ReportVersionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ReportVersionOut], classified("internal")]


class ReportDiffOut(BaseModel):
    """A word diff of two versions through C11 compare."""

    model_config = ConfigDict(frozen=True)

    from_version: Annotated[int, classified("internal")]
    to_version: Annotated[int, classified("internal")]
    inserted_words: Annotated[int, Field(ge=0), classified("internal")]
    deleted_words: Annotated[int, Field(ge=0), classified("internal")]
    compare_document_id: Annotated[UUID | None, classified("internal")]


class ReportChoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]
    value: Annotated[str | bool | None, classified("internal")]
    reason_code: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    seen_version: Annotated[int, classified("internal")]


class ReportDecisionRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Annotated[Literal["opinion"], classified("internal")]


class ReportDocumentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Annotated[Literal["docx", "pdf"], classified("internal")]
    report_version: Annotated[int, Field(ge=1), classified("internal")]


class ReportReasonCodeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Internal  # ERISA-SUPP, EOM-GC, EOM-CHG, OM-OTHER (database content)
    label: Internal
    applies_to: Annotated[list[str], classified("internal")]


class ReasonCodesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ReportReasonCodeOut], classified("internal")]


# --- issuance and release, filings (AUD-24) ------------------------------------------------------


class GateCardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate: Annotated[Gate, classified("internal")]
    met: Annotated[bool, classified("internal")]
    required: Annotated[bool, classified("internal")]
    value: Annotated[str | None, classified("internal")]  # e.g. "Concurred Oct 5, 2026"
    blockers: Annotated[list[str], classified("internal")]


class AlsoRequiredOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Internal  # fs_approved, bring_down, independence, final_materiality, governance_260
    met: Annotated[bool, classified("internal")]
    value: Annotated[str | None, classified("internal")]


class FilingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    form: Annotated[Literal["form_5500"], classified("internal")]
    channel: Annotated[Literal["efast2"], classified("internal")]
    filer_name: Annotated[str, classified("confidential")]
    due_on: Annotated[date | None, classified("internal")]
    extended_due_on: Annotated[date | None, classified("internal")]
    status: Annotated[Literal["awaiting_client_filing", "filed"], classified("internal")]
    filed_on: Annotated[date | None, classified("internal")]
    ack_evidence_version_id: Annotated[UUID | None, classified("internal")]
    version: Annotated[int, classified("internal")]


class AuditReleaseOut(BaseModel):
    """GET …/release: gates with live values, the also-required list and who may release."""

    model_config = ConfigDict(frozen=True)

    gates: Annotated[list[GateCardOut], classified("internal")]
    also_required: Annotated[list[AlsoRequiredOut], classified("internal")]
    gate_hash: Sha256  # what the attestation saw (seen_gate_hash)
    can_release: Annotated[bool, classified("internal")]
    viewer_can_release: Annotated[bool, classified("internal")]
    engagement_partner_name: Internal  # "Only <EP> can release this report" (AUD-24 e)
    released_at: Annotated[datetime | None, classified("internal")]
    released_by_name: Annotated[str | None, classified("internal")]
    documentation_completion_date: Annotated[date | None, classified("internal")]
    deliverable_ids: Annotated[list[UUID], classified("internal")]
    filings: Annotated[list[FilingOut], classified("internal")]
    allowed_actions: Annotated[list[ReportAction], classified("internal")]


class ReleaseIn(BaseModel):
    """G8: "I am the engagement partner and I authorize release of this report"."""

    model_config = ConfigDict(extra="forbid")

    authorize: Annotated[Literal[True], classified("internal")]
    seen_gate_hash: Sha256


class FilingsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[FilingOut], classified("internal")]


class FilingIn(BaseModel):
    """Manual EFAST2 tracking; `filed` needs the date and the acknowledgement evidence."""

    model_config = ConfigDict(extra="forbid")

    status: Annotated[Literal["awaiting_client_filing", "filed"], classified("internal")]
    filed_on: Annotated[date | None, classified("internal")] = None
    ack_evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    seen_version: Annotated[int, classified("internal")]


# --- assembly and archive (AUD-25) ---------------------------------------------------------------


class ArchiveChecklistItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Internal
    title: Internal
    done: Annotated[bool, classified("internal")]
    detail: Annotated[str | None, classified("internal")]


class BinderSectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: Annotated[Literal["A", "B", "C", "D", "E", "F", "G", "H"], classified("internal")]
    title: Internal
    workpapers: Annotated[int, Field(ge=0), classified("internal")]
    source_documents: Annotated[int, Field(ge=0), classified("internal")]
    run_logs: Annotated[int, Field(ge=0), classified("internal")]


class ArchiveAdditionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    reason_code: Annotated[AdditionReason, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    content_sha256: Sha256
    added_by_name: Internal
    added_at: Annotated[datetime, classified("internal")]
    decision: Annotated[Literal["pending", "approved", "rejected"], classified("internal")]
    decided_by_name: Annotated[str | None, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")]


class AuditArchiveStateOut(BaseModel):
    """GET …/archive: the 60-day clock, nine items, the binder index, additions and the seal."""

    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["assembling", "locking", "locked"] | None, classified("internal")]
    release_date: Annotated[date | None, classified("internal")]
    documentation_completion_date: Annotated[date | None, classified("internal")]  # release + 60
    days_left: Annotated[int | None, classified("internal")]
    retention_until: Annotated[date | None, classified("internal")]  # >= release + 5 years
    on_hold: Annotated[bool, classified("internal")]  # a hold never blocks a lock (OQ-10)
    checklist: Annotated[list[ArchiveChecklistItemOut], classified("internal")]
    checklist_done: Annotated[int, Field(ge=0), classified("internal")]
    checklist_total: Annotated[int, Field(ge=0), classified("internal")]
    checklist_hash: Sha256
    binder: Annotated[list[BinderSectionOut], classified("internal")]
    locked_at: Annotated[datetime | None, classified("internal")]
    locked_by_name: Annotated[str | None, classified("internal")]
    seal_sha256: Annotated[str | None, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    additions: Annotated[list[ArchiveAdditionOut], classified("internal")]
    allowed_actions: Annotated[list[ArchiveAction], classified("internal")]


class ArchiveLockIn(BaseModel):
    """G9: "Assembly is complete"; manager or EP; fresh MFA; 9 of 9."""

    model_config = ConfigDict(extra="forbid")

    assembly_complete: Annotated[Literal[True], classified("internal")]
    then_roll_forward: Annotated[bool, classified("internal")] = False  # R2: hand-off to ENG-13
    seen_checklist_hash: Sha256


class ArchiveManifestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_version: Annotated[int, Field(ge=1), classified("internal")]
    canonicalization: Annotated[Literal["rfc8785"], classified("internal")]
    evidence_leaf_count: Annotated[int, Field(ge=0), classified("internal")]
    row_leaf_count: Annotated[int, Field(ge=0), classified("internal")]
    run_record_count: Annotated[int, Field(ge=0), classified("internal")]
    audit_checkpoint_seq_to: Annotated[int, Field(ge=0), classified("internal")]
    audit_checkpoint_root: Sha256
    merkle_root: Sha256
    manifest_sha256: Sha256  # = the seal
    compliance_retain_until: Annotated[date, classified("internal")]  # release + 5 years (OQ-3)
    governance_retain_until: Annotated[date, classified("internal")]  # retention_until


class ArchiveAdditionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ArchiveAdditionOut], classified("internal")]


class ArchiveAdditionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
    reason_code: Annotated[AdditionReason, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]


class ArchiveAdditionRejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]


# --- the routes ----------------------------------------------------------------------------------


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str) -> None:
    """Client 404; the action on the work item's engagement, the work item in the resource."""
    if ctx.client:
        raise NotFound("audit")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, replace(ref.resource(), work_item_id=work_item_id))


def _not_yet() -> NoReturn:
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1/audits/{work_item_id}", tags=["audit release"])
_RL = "/representation-letter"
_GC = "/governance-communications"


@router.get(_RL, action="rep_letter.read", response_model=RepresentationLetterOut, errors=(501,))
async def representation_letter_route(work_item_id: UUID, ctx: Ctx) -> RepresentationLetterOut:
    """AUD-21: structure, paper, signers and the G7 date check (A-07-T24)."""
    await _gate(ctx, work_item_id, "rep_letter.read")
    _not_yet()


@router.get(
    f"{_RL}/versions",
    action="rep_letter.read",
    response_model=list[RepresentationLetterVersionOut],
    errors=(501,),
)
async def representation_letter_versions_route(
    work_item_id: UUID, ctx: Ctx
) -> list[RepresentationLetterVersionOut]:
    await _gate(ctx, work_item_id, "rep_letter.read")
    _not_yet()


@router.get(
    f"{_RL}/versions/{{version_no}}",
    action="rep_letter.read",
    response_model=RepresentationLetterOut,
    errors=(501,),
)
async def representation_letter_version_route(
    work_item_id: UUID, version_no: int, ctx: Ctx
) -> RepresentationLetterOut:
    await _gate(ctx, work_item_id, "rep_letter.read")
    _not_yet()


@router.post(
    f"{_RL}/compose",
    action="rep_letter.draft",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def representation_letter_compose_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """LetterComposeWorkflow: template paragraphs and trigger rules over findings and the SUM."""
    await _gate(ctx, work_item_id, "rep_letter.draft")
    _not_yet()


@router.patch(
    f"{_RL}/representations/{{key}}",
    action="rep_letter.draft",
    response_model=RepresentationLetterOut,
    errors=(409, 501),
)
async def representation_toggle_route(
    work_item_id: UUID, key: str, body: RepresentationToggleIn, ctx: Ctx
) -> RepresentationLetterOut:
    """A toggle is a new working version; general paragraphs are locked (409)."""
    await _gate(ctx, work_item_id, "rep_letter.draft")
    _not_yet()


@router.put(
    f"{_RL}/paragraphs/{{key}}",
    action="rep_letter.draft",
    response_model=RepresentationLetterOut,
    errors=(409, 501),
)
async def representation_paragraph_route(
    work_item_id: UUID, key: str, body: LetterParagraphIn, ctx: Ctx
) -> RepresentationLetterOut:
    """Firm-editable paragraphs only; 422 `internal_amount_in_text` for a materiality amount."""
    await _gate(ctx, work_item_id, "rep_letter.draft")
    _not_yet()


@router.post(
    f"{_RL}/request-approval",
    action="rep_letter.request_approval",
    response_model=RepresentationLetterOut,
    errors=(409, 501),
)
async def representation_request_approval_route(
    work_item_id: UUID, ctx: Ctx
) -> RepresentationLetterOut:
    await _gate(ctx, work_item_id, "rep_letter.request_approval")
    _not_yet()


@router.post(
    f"{_RL}/versions/{{version_no}}/approve",
    action="rep_letter.approve",
    response_model=RepresentationLetterOut,
    errors=(409, 501),
)
async def representation_approve_route(
    work_item_id: UUID, version_no: int, body: LetterApproveIn, ctx: Ctx
) -> RepresentationLetterOut:
    """The EP approves and locks the version (human only, fresh MFA; 409 `content_changed`)."""
    await _gate(ctx, work_item_id, "rep_letter.approve")
    _not_yet()


@router.post(
    f"{_RL}/send",
    action="rep_letter.send",
    response_model=RepresentationLetterOut,
    status_code=201,
    errors=(409, 501),
)
async def representation_send_route(
    work_item_id: UUID, body: LetterSendIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RepresentationLetterOut:
    """C7 envelope dated as of the report date; 409 `approval_required` before approval."""
    await _gate(ctx, work_item_id, "rep_letter.send")
    _not_yet()


@router.post(
    f"{_RL}/remind",
    action="envelope.remind",
    response_model=RepresentationLetterOut,
    errors=(409, 501),
)
async def representation_remind_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RepresentationLetterOut:
    await _gate(ctx, work_item_id, "envelope.remind")
    _not_yet()


@router.post(
    f"{_RL}/re-date",
    action="rep_letter.send",
    response_model=RepresentationLetterOut,
    status_code=201,
    errors=(409, 501),
)
async def representation_redate_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RepresentationLetterOut:
    """Start re-date: a bring-down letter after a date mismatch."""
    await _gate(ctx, work_item_id, "rep_letter.send")
    _not_yet()


@router.get(_GC, action="governance_comm.read", response_model=GovernanceListOut, errors=(501,))
async def governance_list_route(work_item_id: UUID, ctx: Ctx) -> GovernanceListOut:
    """AUD-22: rows with clocks; Overdue derived from the due date (A-07-T26)."""
    await _gate(ctx, work_item_id, "governance_comm.read")
    _not_yet()


@router.post(
    _GC,
    action="governance_comm.draft",
    response_model=GovernanceCommunicationOut,
    status_code=201,
    errors=(409, 501),
)
async def governance_create_route(
    work_item_id: UUID, body: GovernanceCreateIn, ctx: Ctx
) -> GovernanceCommunicationOut:
    await _gate(ctx, work_item_id, "governance_comm.draft")
    _not_yet()


@router.get(
    f"{_GC}/{{communication_id}}",
    action="governance_comm.read",
    response_model=GovernanceCommunicationOut,
    errors=(501,),
)
async def governance_route(
    work_item_id: UUID, communication_id: UUID, ctx: Ctx
) -> GovernanceCommunicationOut:
    await _gate(ctx, work_item_id, "governance_comm.read")
    _not_yet()


@router.post(
    f"{_GC}/{{communication_id}}/compose",
    action="governance_comm.draft",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def governance_compose_route(
    work_item_id: UUID, communication_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """Compose or regenerate; a section-level merge keeps human edits."""
    await _gate(ctx, work_item_id, "governance_comm.draft")
    _not_yet()


@router.patch(
    f"{_GC}/{{communication_id}}/sections/{{key}}",
    action="governance_comm.draft",
    response_model=GovernanceCommunicationOut,
    errors=(409, 501),
)
async def governance_section_route(
    work_item_id: UUID, communication_id: UUID, key: str, body: GovernanceSectionIn, ctx: Ctx
) -> GovernanceCommunicationOut:
    await _gate(ctx, work_item_id, "governance_comm.draft")
    _not_yet()


@router.post(
    f"{_GC}/{{communication_id}}/request-approval",
    action="governance_comm.request_approval",
    response_model=GovernanceCommunicationOut,
    errors=(409, 501),
)
async def governance_request_approval_route(
    work_item_id: UUID, communication_id: UUID, ctx: Ctx
) -> GovernanceCommunicationOut:
    await _gate(ctx, work_item_id, "governance_comm.request_approval")
    _not_yet()


@router.post(
    f"{_GC}/{{communication_id}}/approve-and-send",
    action="governance_comm.approve_send",
    response_model=GovernanceCommunicationOut,
    status_code=201,
    errors=(409, 501),
)
async def governance_approve_send_route(
    work_item_id: UUID,
    communication_id: UUID,
    body: GovernanceSendIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> GovernanceCommunicationOut:
    """The EP approves and sends with fresh MFA (human only); output checks refuse materiality
    in a planning letter and the words 'SAS 114'."""
    await _gate(ctx, work_item_id, "governance_comm.approve_send")
    _not_yet()


@router.get(
    "/governance-recipients",
    action="governance_comm.read",
    response_model=GovernanceRecipientsOut,
    errors=(501,),
)
async def governance_recipients_route(work_item_id: UUID, ctx: Ctx) -> GovernanceRecipientsOut:
    await _gate(ctx, work_item_id, "governance_comm.read")
    _not_yet()


@router.put(
    "/governance-recipients",
    action="governance_comm.manage_recipients",
    response_model=GovernanceRecipientsOut,
    errors=(409, 501),
)
async def governance_recipients_put_route(
    work_item_id: UUID, body: GovernanceRecipientsIn, ctx: Ctx
) -> GovernanceRecipientsOut:
    await _gate(ctx, work_item_id, "governance_comm.manage_recipients")
    _not_yet()


@router.get("/report", action="report.read", response_model=AuditReportOut, errors=(501,))
async def audit_report_route(work_item_id: UUID, ctx: Ctx) -> AuditReportOut:
    """AUD-23: choices, paper, documents and approvals (A-07-T27). No release here."""
    await _gate(ctx, work_item_id, "report.read")
    _not_yet()


@router.get(
    "/report/versions", action="report.read", response_model=ReportVersionsOut, errors=(501,)
)
async def audit_report_versions_route(work_item_id: UUID, ctx: Ctx) -> ReportVersionsOut:
    await _gate(ctx, work_item_id, "report.read")
    _not_yet()


@router.get(
    "/report/versions/{from_version}/diff/{to_version}",
    action="report.read",
    response_model=ReportDiffOut,
    errors=(501,),
)
async def audit_report_diff_route(
    work_item_id: UUID, from_version: int, to_version: int, ctx: Ctx
) -> ReportDiffOut:
    await _gate(ctx, work_item_id, "report.read")
    _not_yet()


@router.get(
    "/report/reason-codes", action="report.read", response_model=ReasonCodesOut, errors=(501,)
)
async def audit_report_reason_codes_route(work_item_id: UUID, ctx: Ctx) -> ReasonCodesOut:
    """The firm's reason-code catalogue for this engagement type (database content)."""
    await _gate(ctx, work_item_id, "report.read")
    _not_yet()


@router.patch(
    "/report/choices", action="report.draft", response_model=AuditReportOut, errors=(409, 501)
)
async def audit_report_choice_route(
    work_item_id: UUID, body: ReportChoiceIn, ctx: Ctx
) -> AuditReportOut:
    """A validated choice is a new version; a modified opinion without the EP's decided card
    answers 409 `decision_required`."""
    await _gate(ctx, work_item_id, "report.draft")
    _not_yet()


@router.post(
    "/report/request-decision",
    action="report.request_decision",
    response_model=AuditReportOut,
    status_code=201,
    errors=(409, 501),
)
async def audit_report_request_decision_route(
    work_item_id: UUID, body: ReportDecisionRequestIn, ctx: Ctx
) -> AuditReportOut:
    """Raise the `opinion` card for the EP (C3)."""
    await _gate(ctx, work_item_id, "report.request_decision")
    _not_yet()


@router.post(
    "/report/documents",
    action="report.generate",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def audit_report_document_route(
    work_item_id: UUID, body: ReportDocumentIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """A draft render through C11 (DRAFT watermark, signature placeholder; byte-identical)."""
    await _gate(ctx, work_item_id, "report.generate")
    _not_yet()


@router.get("/release", action="report.read", response_model=AuditReleaseOut, errors=(501,))
async def audit_release_route(work_item_id: UUID, ctx: Ctx) -> AuditReleaseOut:
    """AUD-24: G5-G7 with live values, the also-required list, deliverables, filings (A-07-T30)."""
    await _gate(ctx, work_item_id, "report.read")
    _not_yet()


@router.post(
    "/release",
    action="report.release",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def audit_release_post_route(
    work_item_id: UUID, body: ReleaseIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """G8 through ReleaseWorkflow: the EP only, fresh MFA, the gates re-checked at the server
    (409 `gates_not_met`, `content_changed`); no hold and no Undo (DEC-2260)."""
    await _gate(ctx, work_item_id, "report.release")
    _not_yet()


@router.get("/filings", action="report.read", response_model=FilingsOut, errors=(501,))
async def audit_filings_route(work_item_id: UUID, ctx: Ctx) -> FilingsOut:
    await _gate(ctx, work_item_id, "report.read")
    _not_yet()


@router.patch(
    "/filings/{filing_id}", action="filing.update", response_model=FilingOut, errors=(409, 501)
)
async def audit_filing_route(
    work_item_id: UUID, filing_id: UUID, body: FilingIn, ctx: Ctx
) -> FilingOut:
    """Manual EFAST2 tracking (A-07-T36); Accrued never files."""
    await _gate(ctx, work_item_id, "filing.update")
    _not_yet()


@router.get("/archive", action="archive.read", response_model=AuditArchiveStateOut, errors=(501,))
async def audit_archive_route(work_item_id: UUID, ctx: Ctx) -> AuditArchiveStateOut:
    """AUD-25: the clock, nine items, the binder index, additions and the seal (A-07-T31)."""
    await _gate(ctx, work_item_id, "archive.read")
    _not_yet()


@router.post(
    "/archive/binder-index",
    action="archive.build_index",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def audit_archive_index_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """ArchiveReadinessWorkflow (#4302): the binder index over A-01's export sections."""
    await _gate(ctx, work_item_id, "archive.build_index")
    _not_yet()


@router.post(
    "/archive/request-lock",
    action="archive.request_lock",
    response_model=AuditArchiveStateOut,
    errors=(409, 501),
)
async def audit_archive_request_lock_route(work_item_id: UUID, ctx: Ctx) -> AuditArchiveStateOut:
    """A senior or above notifies the manager (409 `checklist_incomplete` before 9 of 9)."""
    await _gate(ctx, work_item_id, "archive.request_lock")
    _not_yet()


@router.post(
    "/archive/lock",
    action="archive.lock",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def audit_archive_lock_route(
    work_item_id: UUID, body: ArchiveLockIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """G9: the lock decision and ArchiveLockWorkflow (seal, COMPLIANCE manifest; A-07-T37)."""
    await _gate(ctx, work_item_id, "archive.lock")
    _not_yet()


@router.get(
    "/archive/manifest", action="archive.read", response_model=ArchiveManifestOut, errors=(501,)
)
async def audit_archive_manifest_route(work_item_id: UUID, ctx: Ctx) -> ArchiveManifestOut:
    await _gate(ctx, work_item_id, "archive.read")
    _not_yet()


@router.get(
    "/archive/additions", action="archive.read", response_model=ArchiveAdditionsOut, errors=(501,)
)
async def audit_archive_additions_route(work_item_id: UUID, ctx: Ctx) -> ArchiveAdditionsOut:
    await _gate(ctx, work_item_id, "archive.read")
    _not_yet()


@router.post(
    "/archive/additions",
    action="archive_addition.create",
    response_model=ArchiveAdditionOut,
    status_code=201,
    errors=(409, 501),
)
async def audit_archive_addition_route(
    work_item_id: UUID, body: ArchiveAdditionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ArchiveAdditionOut:
    """ "Add after lock…" (pending until the EP decides; A-07-T42)."""
    await _gate(ctx, work_item_id, "archive_addition.create")
    _not_yet()


@router.post(
    "/archive/additions/{addition_id}/approve",
    action="archive_addition.approve",
    response_model=ArchiveAdditionOut,
    errors=(409, 501),
)
async def audit_archive_addition_approve_route(
    work_item_id: UUID, addition_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ArchiveAdditionOut:
    """The EP approves with fresh MFA under the `archive_addition` exception kind."""
    await _gate(ctx, work_item_id, "archive_addition.approve")
    _not_yet()


@router.post(
    "/archive/additions/{addition_id}/reject",
    action="archive_addition.approve",
    response_model=ArchiveAdditionOut,
    errors=(409, 501),
)
async def audit_archive_addition_reject_route(
    work_item_id: UUID, addition_id: UUID, body: ArchiveAdditionRejectIn, ctx: Ctx
) -> ArchiveAdditionOut:
    await _gate(ctx, work_item_id, "archive_addition.approve")
    _not_yet()


@router.post(
    "/archive/verify",
    action="archive.verify",
    response_model=ReleaseRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def audit_archive_verify_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReleaseRunAcceptedOut:
    """SealVerifyWorkflow: "Seal verified" or `seal_mismatch` with an RB-29 alert."""
    await _gate(ctx, work_item_id, "archive.verify")
    _not_yet()
