"""The A-07 contract stub, part 1: AUD-18 and AUD-19 (A-07-T04; SPEC-644; DEC-2230).
Contract: `docs/contracts/audit-completion.md` (EQR; completion, subsequent events, legal
letters and going concern).

Every route is under `/v1/audits/{work_item_id}` (the assurance work item, A-01), has one matrix
action and answers, in order: a client principal 404 (INV-4); 404 for a work item that is not an
assurance work item; the action on the work item's engagement with the work item in the resource
(walls 404, independence 403, `function_in(eqr)` for the EQR's acts); then 501 `not_implemented`
until its task (A-07-T18, T22, T23) and the Jan 27, 2028 flag `audits.completion` (A-07-T33).

Code computes every figure (ADR-050): the digest's rows come from decided cards and conclusions,
the counts exclude not-applicable rows, going concern's DSCR and covenant are code's. Concurrence
is the assigned EQR's five-layer human-only act with fresh MFA; going concern is the engagement
partner's C3 card (`going_concern`), decided through `POST /v1/decisions/{id}/decide`, never here
(INV-1). SPEC-314's record-mode routes stay live until A-07-T33 (DEC-2261).
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
Text = Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
Internal = Annotated[str, classified("internal")]
Gate = Literal["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]
EqrAction = Literal[
    "eqr.build_digest", "eqr.mark_reviewed", "eqr.checklist_update", "eqr.concur", "eqr.request",
    "review_note.create", "review_note.respond", "review_note.clear",
]  # fmt: skip
CompletionAction = Literal[
    "completion.update", "subsequent_event.create", "subsequent_event.update",
    "legal_letter.update", "legal_letter.request", "going_concern.request_decision",
]  # fmt: skip


class CompletionKvOut(BaseModel):
    """One code-computed label and value (a digest card row, a going-concern input)."""

    model_config = ConfigDict(frozen=True)

    label: Internal
    value: Annotated[str, classified("confidential")]


class CompletionRunAcceptedOut(BaseModel):
    """202: a code-only run started (EqrDigestWorkflow, CompletionReadiness, BringDown)."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    status_url: Internal


# --- EQR (AUD-18) --------------------------------------------------------------------------------


class EqrChecklistItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_key: Internal
    position: Annotated[int, Field(ge=1), classified("internal")]
    title: Internal  # the firm template's wording (database content)
    status: Annotated[Literal["todo", "partial", "done"], classified("internal")]
    sub_line: Annotated[str | None, classified("confidential")]
    updated_by_name: Annotated[str | None, classified("internal")]
    version: Annotated[int, classified("internal")]


class EqrDigestCardOut(BaseModel):
    """A card built by code from one decided card or conclusion; rebuilt cards supersede."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    source_kind: Annotated[Literal["decision", "conclusion"], classified("internal")]
    source_ref: Internal  # e.g. the decision card's id or the conclusion's object ref
    title: Internal
    rows: Annotated[list[CompletionKvOut], classified("confidential")]
    snapshot_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    link_target: Internal  # the read-only source screen (AUD-07/08/10/15/16/20/23)
    reviewed_at: Annotated[datetime | None, classified("internal")]
    reviewed_by_name: Annotated[str | None, classified("internal")]


class EqrNoteRowOut(BaseModel):
    """An EQR note (a C3 review note of kind `eqr`), summarised for the rail."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, Field(pattern=r"^EQR-[0-9]{1,3}$"), classified("internal")]
    status: Annotated[Literal["open", "responded", "cleared"], classified("internal")]
    assignee_name: Annotated[str | None, classified("internal")]


class EqrConcurrenceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    concurred_by_name: Internal
    concurred_at: Annotated[datetime, classified("internal")]
    concurrence_date: Annotated[date, classified("internal")]
    not_involved_attested: Annotated[Literal[True], classified("internal")]


class EqrReviewOut(BaseModel):
    """GET …/eqr: the review, its checklist, digest cards, notes and what blocks concurrence."""

    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    required: Annotated[bool, classified("internal")]  # from the ENG-05 assignment (OQ-7)
    eqr_name: Annotated[str | None, classified("internal")]
    status: Annotated[
        Literal["in_progress", "ready_to_concur", "concurred"], classified("internal")
    ]
    checklist: Annotated[list[EqrChecklistItemOut], classified("internal")]
    checklist_done: Annotated[int, Field(ge=0), classified("internal")]
    checklist_total: Annotated[int, Field(ge=0), classified("internal")]
    digest_cards: Annotated[list[EqrDigestCardOut], classified("internal")]
    notes: Annotated[list[EqrNoteRowOut], classified("internal")]
    concurrence: Annotated[EqrConcurrenceOut | None, classified("internal")]
    # e.g. "checklist_open:4", "eqr_notes_open:2", "not_assigned_eqr"; fixed words in the UI
    blockers: Annotated[list[str], classified("internal")]
    viewer_is_eqr: Annotated[bool, classified("internal")]
    allowed_actions: Annotated[list[EqrAction], classified("internal")]
    version: Annotated[int, classified("internal")]


class EqrChecklistIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Annotated[Literal["todo", "partial", "done"], classified("internal")]
    sub_line: Annotated[str | None, Field(max_length=280), classified("confidential")] = None
    seen_version: Annotated[int, classified("internal")]


class EqrCardReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewed: Annotated[bool, classified("internal")]


class EqrConcurIn(BaseModel):
    """G6: only the assigned EQR, 10 of 10, notes cleared, attested, fresh MFA."""

    model_config = ConfigDict(extra="forbid")

    not_involved: Annotated[Literal[True], classified("internal")]
    concurrence_date: Annotated[date, classified("internal")]
    seen_version: Annotated[int, classified("internal")]


class EqrRequestIn(BaseModel):
    """ "Request EQR…" (DF-05, DV-4)."""

    model_config = ConfigDict(extra="forbid")

    message: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None


# --- completion (AUD-19) -------------------------------------------------------------------------


class AuditCompletionItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_key: Internal
    position: Annotated[int, Field(ge=1), classified("internal")]
    title: Internal  # the firm template's wording (database content)
    status: Annotated[Literal["open", "partial", "done", "not_applicable"], classified("internal")]
    derived: Annotated[
        bool, classified("internal")
    ]  # projected from events; manual N/A only if not
    evidence_text: Annotated[str | None, classified("confidential")]
    link_target: Annotated[str | None, classified("internal")]
    gate_tag: Annotated[Gate | None, classified("internal")]
    depends_on_client: Annotated[bool, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]
    na_basis: Annotated[str | None, classified("confidential")]
    na_by_name: Annotated[str | None, classified("internal")]


class AuditCompletionOut(BaseModel):
    """GET …/completion: items, counts with N/A excluded ("12 of 17"), what blocks the report."""

    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    items: Annotated[list[AuditCompletionItemOut], classified("internal")]
    complete: Annotated[int, Field(ge=0), classified("internal")]
    not_applicable: Annotated[int, Field(ge=0), classified("internal")]
    open: Annotated[int, Field(ge=0), classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]  # excludes not applicable
    blockers: Annotated[list[str], classified("internal")]  # item keys, in checklist order
    allowed_actions: Annotated[list[CompletionAction], classified("internal")]
    version: Annotated[int, classified("internal")]


class CompletionItemNaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis: Text
    seen_version: Annotated[int, classified("internal")]


class CompletionItemReopenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seen_version: Annotated[int, classified("internal")]


class SubsequentEventProcedureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    procedure_key: Internal
    title: Internal
    performed_through: Annotated[date | None, classified("internal")]
    performed_by_name: Annotated[str | None, classified("internal")]
    status: Annotated[Literal["open", "performed"], classified("internal")]
    run_id: Annotated[UUID | None, classified("internal")]


class SubsequentEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    recognition: Annotated[Literal["recognized", "nonrecognized"], classified("internal")]
    fs_effect: Annotated[str | None, classified("confidential")]
    note_ref: Annotated[str | None, classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    recorded_by_name: Internal
    recorded_at: Annotated[datetime, classified("internal")]


class BringDownOut(BaseModel):
    """The report-date bring-down run (BringDownWorkflow, 09:00 firm time on the report date)."""

    model_config = ConfigDict(frozen=True)

    scheduled_for: Annotated[datetime | None, classified("internal")]
    run_id: Annotated[UUID | None, classified("internal")]
    status: Annotated[Literal["not_scheduled", "queued", "completed"], classified("internal")]


class SubsequentEventsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_date: Annotated[date | None, classified("internal")]
    procedures: Annotated[list[SubsequentEventProcedureOut], classified("internal")]
    events: Annotated[list[SubsequentEventOut], classified("internal")]
    bring_down: Annotated[BringDownOut, classified("internal")]
    allowed_actions: Annotated[list[CompletionAction], classified("internal")]


class SubsequentEventProcedureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procedure_key: Annotated[str, Field(min_length=1, max_length=80), classified("internal")]


class SubsequentEventProcedureUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performed_through: Annotated[date, classified("internal")]
    status: Annotated[Literal["open", "performed"], classified("internal")]
    seen_version: Annotated[int, classified("internal")]


class SubsequentEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Text
    recognition: Annotated[Literal["recognized", "nonrecognized"], classified("internal")]
    fs_effect: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    note_ref: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    citation_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []


class LegalLetterOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[
        Literal["not_applicable", "requested", "received"] | None, classified("internal")
    ]
    not_applicable: Annotated[bool, classified("internal")]
    basis: Annotated[str | None, classified("confidential")]
    request_item_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Annotated[list[CompletionAction], classified("internal")]
    version: Annotated[int, classified("internal")]


class LegalLetterIn(BaseModel):
    """Not applicable needs a basis (CHECK `not_applicable = (basis IS NOT NULL)`)."""

    model_config = ConfigDict(extra="forbid")

    not_applicable: Annotated[bool, classified("internal")]
    basis: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    seen_version: Annotated[int, classified("internal")]


class LegalLetterRequestIn(BaseModel):
    """An SHL-14 third-party request to counsel through P-06."""

    model_config = ConfigDict(extra="forbid")

    counsel_contact_id: Annotated[UUID, classified("internal")]
    message: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None


class GoingConcernOut(BaseModel):
    """The EP's `going_concern` card and code's inputs (Granite Peak: DSCR 1.32x vs 1.25x)."""

    model_config = ConfigDict(frozen=True)

    state: Annotated[
        Literal["not_requested", "awaiting_decision", "decided"], classified("internal")
    ]
    decision_card_id: Annotated[UUID | None, classified("internal")]
    conclusion: Annotated[
        Literal["no_substantial_doubt", "doubt_alleviated", "doubt_exists"] | None,
        classified("internal"),
    ]
    decided_by_name: Annotated[str | None, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")]
    inputs: Annotated[list[CompletionKvOut], classified("confidential")]
    reserved_to: Annotated[Literal["engagement_partner"], classified("internal")]
    allowed_actions: Annotated[list[CompletionAction], classified("internal")]


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


router = AbacusRouter(prefix="/v1/audits/{work_item_id}", tags=["audit completion"])


@router.get("/eqr", action="eqr.read", response_model=EqrReviewOut, errors=(501,))
async def eqr_review_route(work_item_id: UUID, ctx: Ctx) -> EqrReviewOut:
    """AUD-18: checklist, digest cards, EQR notes and the concurrence blockers (A-07-T18)."""
    await _gate(ctx, work_item_id, "eqr.read")
    _not_yet()


@router.post(
    "/eqr/digest:build",
    action="eqr.build_digest",
    response_model=CompletionRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def eqr_digest_build_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> CompletionRunAcceptedOut:
    """Starts EqrDigestWorkflow (code only; A-07-T18, T32)."""
    await _gate(ctx, work_item_id, "eqr.build_digest")
    _not_yet()


@router.post(
    "/eqr/digest/{card_id}/reviewed",
    action="eqr.mark_reviewed",
    response_model=EqrDigestCardOut,
    errors=(409, 501),
)
async def eqr_card_reviewed_route(
    work_item_id: UUID, card_id: UUID, body: EqrCardReviewIn, ctx: Ctx
) -> EqrDigestCardOut:
    """The assigned EQR marks a card reviewed (403 `eqr_only` otherwise; A-07-T18)."""
    await _gate(ctx, work_item_id, "eqr.mark_reviewed")
    _not_yet()


@router.patch(
    "/eqr/checklist/{item_key}",
    action="eqr.checklist_update",
    response_model=EqrChecklistItemOut,
    errors=(409, 501),
)
async def eqr_checklist_route(
    work_item_id: UUID, item_key: str, body: EqrChecklistIn, ctx: Ctx
) -> EqrChecklistItemOut:
    await _gate(ctx, work_item_id, "eqr.checklist_update")
    _not_yet()


@router.post(
    "/eqr/concur",
    action="eqr.concur",
    response_model=EqrReviewOut,
    status_code=201,
    errors=(409, 501),
)
async def eqr_concur_route(
    work_item_id: UUID, body: EqrConcurIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EqrReviewOut:
    """G6. Refused while any item or EQR note is open (409 `checklist_incomplete`), for anyone but
    the assigned EQR (403 `eqr_only`), without a fresh second factor (401 `mfa_required`)."""
    await _gate(ctx, work_item_id, "eqr.concur")
    _not_yet()


@router.post("/eqr/request", action="eqr.request", response_model=EqrReviewOut, errors=(409, 501))
async def eqr_request_route(work_item_id: UUID, body: EqrRequestIn, ctx: Ctx) -> EqrReviewOut:
    """ "Request EQR…" from AUD-23 while an EQR is required and not concurred (DF-05)."""
    await _gate(ctx, work_item_id, "eqr.request")
    _not_yet()


@router.get(
    "/completion", action="completion.read", response_model=AuditCompletionOut, errors=(501,)
)
async def audit_completion_route(work_item_id: UUID, ctx: Ctx) -> AuditCompletionOut:
    """AUD-19 a: the projected checklist (A-07-T22)."""
    await _gate(ctx, work_item_id, "completion.read")
    _not_yet()


@router.post(
    "/completion/items/{item_key}/not-applicable",
    action="completion.update",
    response_model=AuditCompletionItemOut,
    errors=(409, 501),
)
async def completion_item_na_route(
    work_item_id: UUID, item_key: str, body: CompletionItemNaIn, ctx: Ctx
) -> AuditCompletionItemOut:
    """A manager marks a manual item not applicable with a basis (409 `item_derived` on a
    projected item)."""
    await _gate(ctx, work_item_id, "completion.update")
    _not_yet()


@router.post(
    "/completion/items/{item_key}/reopen",
    action="completion.update",
    response_model=AuditCompletionItemOut,
    errors=(409, 501),
)
async def completion_item_reopen_route(
    work_item_id: UUID, item_key: str, body: CompletionItemReopenIn, ctx: Ctx
) -> AuditCompletionItemOut:
    await _gate(ctx, work_item_id, "completion.update")
    _not_yet()


@router.get(
    "/subsequent-events",
    action="completion.read",
    response_model=SubsequentEventsOut,
    errors=(501,),
)
async def subsequent_events_route(work_item_id: UUID, ctx: Ctx) -> SubsequentEventsOut:
    """AUD-19 b: procedures through the report date, events and the bring-down (A-07-T23)."""
    await _gate(ctx, work_item_id, "completion.read")
    _not_yet()


@router.post(
    "/subsequent-events/procedures",
    action="subsequent_event.update",
    response_model=SubsequentEventProcedureOut,
    status_code=201,
    errors=(409, 501),
)
async def subsequent_procedure_add_route(
    work_item_id: UUID, body: SubsequentEventProcedureIn, ctx: Ctx
) -> SubsequentEventProcedureOut:
    await _gate(ctx, work_item_id, "subsequent_event.update")
    _not_yet()


@router.patch(
    "/subsequent-events/procedures/{procedure_id}",
    action="subsequent_event.update",
    response_model=SubsequentEventProcedureOut,
    errors=(409, 501),
)
async def subsequent_procedure_route(
    work_item_id: UUID, procedure_id: UUID, body: SubsequentEventProcedureUpdateIn, ctx: Ctx
) -> SubsequentEventProcedureOut:
    await _gate(ctx, work_item_id, "subsequent_event.update")
    _not_yet()


@router.post(
    "/subsequent-events",
    action="subsequent_event.create",
    response_model=SubsequentEventOut,
    status_code=201,
    errors=(409, 501),
)
async def subsequent_event_route(
    work_item_id: UUID, body: SubsequentEventIn, ctx: Ctx
) -> SubsequentEventOut:
    """Record an event (insert-only); every citation verified by C4 (INV-2)."""
    await _gate(ctx, work_item_id, "subsequent_event.create")
    _not_yet()


@router.get(
    "/legal-letters", action="completion.read", response_model=LegalLetterOut, errors=(501,)
)
async def legal_letters_route(work_item_id: UUID, ctx: Ctx) -> LegalLetterOut:
    await _gate(ctx, work_item_id, "completion.read")
    _not_yet()


@router.put(
    "/legal-letters",
    action="legal_letter.update",
    response_model=LegalLetterOut,
    errors=(409, 501),
)
async def legal_letters_put_route(
    work_item_id: UUID, body: LegalLetterIn, ctx: Ctx
) -> LegalLetterOut:
    """Not applicable with a basis (AUD-19 c)."""
    await _gate(ctx, work_item_id, "legal_letter.update")
    _not_yet()


@router.post(
    "/legal-letters/request",
    action="legal_letter.request",
    response_model=LegalLetterOut,
    status_code=201,
    errors=(409, 501),
)
async def legal_letters_request_route(
    work_item_id: UUID, body: LegalLetterRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> LegalLetterOut:
    """ "Request a legal letter…": an SHL-14 third-party request through P-06."""
    await _gate(ctx, work_item_id, "legal_letter.request")
    _not_yet()


@router.get(
    "/going-concern", action="completion.read", response_model=GoingConcernOut, errors=(501,)
)
async def audit_going_concern_route(work_item_id: UUID, ctx: Ctx) -> GoingConcernOut:
    """AUD-19 d and e: the decided card read-only, "Reserved to Engagement Partner"."""
    await _gate(ctx, work_item_id, "completion.read")
    _not_yet()


@router.post(
    "/going-concern/request-decision",
    action="going_concern.request_decision",
    response_model=GoingConcernOut,
    status_code=201,
    errors=(409, 501),
)
async def going_concern_request_route(work_item_id: UUID, ctx: Ctx) -> GoingConcernOut:
    """Raise the `going_concern` card with code-computed options; the EP decides (P-04)."""
    await _gate(ctx, work_item_id, "going_concern.request_decision")
    _not_yet()
