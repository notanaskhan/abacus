"""The A-07 completion reads (S35 follow-up; A-07-T18, T22, T23, T24 reads): AUD-18's EQR review,
AUD-19's checklist, subsequent events, legal letter and going concern, and AUD-21's letter, over
the rows their services already write.

Read only: no row is written here and no sealed text leaves without its route's authorisation
(the route's `_gate` runs first). Titles and blocker sentences are the firm template's (database
content); figures are code's (ADR-050). A going-concern conclusion is read from the EP's decided
card, never computed (INV-1).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import last_completed_run
from abacus.modules.assurance import completion_projector as projector
from abacus.modules.assurance import eqr_service
from abacus.modules.assurance.agent_capabilities import BRING_DOWN
from abacus.modules.assurance.completion_contract import (
    AuditCompletionItemOut,
    AuditCompletionOut,
    BringDownOut,
    CompletionAction,
    CompletionKvOut,
    EqrAction,
    EqrChecklistItemOut,
    EqrConcurrenceOut,
    EqrDigestCardOut,
    EqrNoteRowOut,
    EqrReviewOut,
    GoingConcernOut,
    LegalLetterOut,
    SubsequentEventOut,
    SubsequentEventProcedureOut,
    SubsequentEventsOut,
)
from abacus.modules.assurance.release_contract import (
    LetterAction,
    LetterParagraphOut,
    LetterRepresentationOut,
    RepresentationLetterOut,
    RepresentationLetterVersionOut,
)
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import AuthContext, allowed_actions, names_of
from abacus.modules.methodology.api import published_checklist, report_template_parts
from abacus.modules.review.api import awaiting_cards, decided_cards, note_states

_COMPLETION_ACTIONS: Final[tuple[CompletionAction, ...]] = (
    "completion.update", "subsequent_event.create", "subsequent_event.update",
    "legal_letter.update", "legal_letter.request", "going_concern.request_decision",
)  # fmt: skip
_SE_ACTIONS: Final[tuple[CompletionAction, ...]] = (
    "subsequent_event.create", "subsequent_event.update",
)  # fmt: skip
_LEGAL_ACTIONS: Final[tuple[CompletionAction, ...]] = (
    "legal_letter.update",
    "legal_letter.request",
)
_GC_ACTIONS: Final[tuple[CompletionAction, ...]] = ("going_concern.request_decision",)
_EQR_ACTIONS: Final[tuple[EqrAction, ...]] = (
    "eqr.build_digest", "eqr.mark_reviewed", "eqr.checklist_update", "eqr.concur", "eqr.request",
    "review_note.create", "review_note.respond", "review_note.clear",
)  # fmt: skip
_LETTER_ACTIONS: Final[tuple[LetterAction, ...]] = (
    "rep_letter.draft", "rep_letter.request_approval", "rep_letter.approve", "rep_letter.send",
    "envelope.remind",
)  # fmt: skip
_MATRIX_NAME: Final[dict[str, str]] = {"review_note.create": "review_note.raise"}
_EQR_ONLY: Final = frozenset({"eqr.mark_reviewed", "eqr.checklist_update", "eqr.concur"})
_NOTE_STATUS: Final[dict[str, Literal["open", "responded", "cleared"]]] = {
    "open": "open",
    "responded": "responded",
    "cleared": "cleared",
    "closed": "cleared",
}
type Conclusion = Literal["no_substantial_doubt", "doubt_alleviated", "doubt_exists"]
_GOING_CONCERN: Final[tuple[Conclusion, ...]] = (
    "no_substantial_doubt", "doubt_alleviated", "doubt_exists",
)  # fmt: skip


def _conclusion(option_key: str) -> Conclusion | None:
    """The EP's option, when it is one of AU-C 570's three (read, never chosen here)."""
    return next((c for c in _GOING_CONCERN if c == option_key), None)


async def _held[A: str](ctx: AuthContext, work_item_id: UUID, wanted: Sequence[A]) -> list[A]:
    """The acts the viewer holds on the work item, in the contract's order (the matrix's)."""
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    held = await allowed_actions(
        ctx, replace(ref.resource(), work_item_id=work_item_id), list(wanted)
    )
    return [a for a in wanted if a in held]


async def _names(ids: Sequence[UUID | None]) -> dict[UUID, str]:
    found = sorted({i for i in ids if i is not None}, key=str)
    return dict(await names_of(found)) if found else {}


async def _unseal(tenant: TenantContext, sealed: bytes | None, fingerprint: str) -> str | None:
    if sealed is None:
        return None
    return (await open_sealed(tenant.tenant_id, bytes(sealed), fingerprint)).decode()


_REPORT_DATE = text(
    "SELECT report_date FROM audit_reports WHERE work_item_id = :wi "
    "ORDER BY updated_at DESC LIMIT 1"
)


async def _report_date(tenant: TenantContext, work_item_id: UUID) -> date | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(_REPORT_DATE, {"wi": work_item_id})
    return found if isinstance(found, date) else None


# --- AUD-19 a: the checklist ---------------------------------------------------------------------

_ITEMS = text(
    "SELECT item_key, position, status, derived, evidence_text, link_target, gate_tag, "
    "depends_on_client, due_on, id, na_basis_sealed, na_by, version FROM completion_items "
    "WHERE work_item_id = :wi ORDER BY position"
)


async def completion(ctx: AuthContext, work_item_id: UUID) -> AuditCompletionOut:
    item = await assurance_item(ctx.tenant, work_item_id)
    template = await published_checklist(
        ctx.tenant,
        "completion",
        projector.engagement_type_of(item.assurance_type, item.ebp_plan_kind),
    )
    wording = {} if template is None else {i.key: i for i in template.items}
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ITEMS, {"wi": work_item_id})).all()
    names = await _names([r.na_by for r in rows])
    items: list[AuditCompletionItemOut] = []
    for r in rows:
        source = wording.get(r.item_key)
        items.append(
            AuditCompletionItemOut(
                item_key=r.item_key,
                position=r.position,
                title=r.item_key if source is None else source.text,
                status=r.status,
                derived=bool(r.derived),
                evidence_text=r.evidence_text,
                link_target=r.link_target,
                gate_tag=r.gate_tag,
                depends_on_client=bool(r.depends_on_client),
                due_on=r.due_on,
                na_basis=await _unseal(ctx.tenant, r.na_basis_sealed, f"completion_item:{r.id}"),
                na_by_name=None if r.na_by is None else names.get(r.na_by),
                blocker_text=None if source is None else (source.blocker or source.text),
            )
        )
    counted = [i for i in items if i.status != "not_applicable"]
    blockers = [i.item_key for i in counted if i.status != "done"]
    return AuditCompletionOut(
        work_item_id=work_item_id,
        items=items,
        complete=sum(1 for i in counted if i.status == "done"),
        not_applicable=len(items) - len(counted),
        open=len(blockers),
        total=len(counted),
        blockers=blockers,
        allowed_actions=await _held(ctx, work_item_id, _COMPLETION_ACTIONS),
        version=sum(int(r.version) for r in rows),
    )


# --- AUD-19 b: subsequent events -----------------------------------------------------------------

_PROCEDURES = text(
    "SELECT id, procedure_key, performed_through, performed_by, status, run_id "
    "FROM subsequent_event_procedures WHERE work_item_id = :wi ORDER BY created_at, id"
)
_EVENTS = text(
    "SELECT id, description_sealed, recognition, fs_effect_sealed, note_ref, citation_ids, "
    "recorded_by, created_at FROM subsequent_events WHERE work_item_id = :wi "
    "ORDER BY created_at, id"
)


async def subsequent_events(ctx: AuthContext, work_item_id: UUID) -> SubsequentEventsOut:
    item = await assurance_item(ctx.tenant, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        procedures = (await session.execute(_PROCEDURES, {"wi": work_item_id})).all()
        events = (await session.execute(_EVENTS, {"wi": work_item_id})).all()
    names = await _names([p.performed_by for p in procedures] + [e.recorded_by for e in events])
    report_date = await _report_date(ctx.tenant, work_item_id)
    run = await last_completed_run(ctx.tenant, item.engagement_id, BRING_DOWN)
    if run is not None:
        bring = BringDownOut(scheduled_for=None, run_id=run[0], status="completed")
    elif report_date is not None and await projector.projector_live(ctx.tenant):
        bring = BringDownOut(scheduled_for=None, run_id=None, status="queued")
    else:
        bring = BringDownOut(scheduled_for=None, run_id=None, status="not_scheduled")
    out_events: list[SubsequentEventOut] = []
    for e in events:
        out_events.append(
            SubsequentEventOut(
                id=e.id,
                description=await _unseal(
                    ctx.tenant, e.description_sealed, f"subsequent_event:{e.id}"
                )
                or "",
                recognition=e.recognition,
                fs_effect=await _unseal(
                    ctx.tenant, e.fs_effect_sealed, f"subsequent_event:{e.id}:fx"
                ),
                note_ref=e.note_ref,
                citation_ids=list(e.citation_ids or []),
                recorded_by_name=names.get(e.recorded_by, ""),
                recorded_at=e.created_at,
            )
        )
    return SubsequentEventsOut(
        report_date=report_date,
        procedures=[
            SubsequentEventProcedureOut(
                id=p.id,
                procedure_key=p.procedure_key,
                # The firm's procedure list carries no wording of its own yet: the key is the
                # label (no invented copy).
                title=p.procedure_key,
                performed_through=p.performed_through,
                performed_by_name=None if p.performed_by is None else names.get(p.performed_by),
                status=p.status,
                run_id=p.run_id,
            )
            for p in procedures
        ],
        events=out_events,
        bring_down=bring,
        allowed_actions=await _held(ctx, work_item_id, _SE_ACTIONS),
    )


# --- AUD-19 c: the legal letter ------------------------------------------------------------------

_LEGAL = text(
    "SELECT not_applicable, basis_sealed, request_item_id, status, version FROM legal_letters "
    "WHERE work_item_id = :wi"
)


async def legal_letter(ctx: AuthContext, work_item_id: UUID) -> LegalLetterOut:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_LEGAL, {"wi": work_item_id})).first()
    actions: list[CompletionAction] = await _held(ctx, work_item_id, _LEGAL_ACTIONS)
    if row is None:
        return LegalLetterOut(
            status=None,
            not_applicable=False,
            basis=None,
            request_item_id=None,
            allowed_actions=actions,
            version=0,
        )
    return LegalLetterOut(
        status=row.status,
        not_applicable=bool(row.not_applicable),
        basis=await _unseal(ctx.tenant, row.basis_sealed, f"legal_letter:{work_item_id}"),
        request_item_id=row.request_item_id,
        allowed_actions=actions,
        version=int(row.version),
    )


# --- AUD-19 d and e: going concern ---------------------------------------------------------------

_EVALUATION = text(
    "SELECT decision_card_id, inputs FROM going_concern_evaluations WHERE work_item_id = :wi"
)


_TIMES: Final = "\u00d7"  # the multiplication sign of AUD-19's ratio copy


def _inputs(raw: object) -> list[CompletionKvOut]:
    """Code's figures, as code computed them (ADR-050): the ratio against the covenant."""
    if raw is None:
        return []
    found = cast("dict[str, object]", raw if isinstance(raw, dict) else json.loads(str(raw)))
    out = [
        CompletionKvOut(
            label="DSCR covenant minimum",
            value=f"{found['covenant_dscr']}{_TIMES}, actual {found['dscr']}{_TIMES}.",
        )
    ]
    if found.get("facility_matures_on"):
        out.append(
            CompletionKvOut(label="Facility matures", value=str(found["facility_matures_on"]))
        )
    return out


async def going_concern(ctx: AuthContext, work_item_id: UUID) -> GoingConcernOut:
    item = await assurance_item(ctx.tenant, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        evaluation = (await session.execute(_EVALUATION, {"wi": work_item_id})).first()
    actions: list[CompletionAction] = await _held(ctx, work_item_id, _GC_ACTIONS)
    subject: Literal["plan", "entity"] = "plan" if item.ebp_plan_kind else "entity"
    inputs = [] if evaluation is None else _inputs(evaluation.inputs)
    awaiting = await awaiting_cards(ctx.tenant, work_item_id, ["going_concern"])
    card_id = None if evaluation is None else evaluation.decision_card_id
    decided = [
        c
        for c in await decided_cards(ctx.tenant, item.engagement_id)
        if c.kind == "going_concern" and (card_id is None or c.card_id == card_id)
    ]
    if awaiting:
        return GoingConcernOut(
            state="awaiting_decision",
            decision_card_id=awaiting[-1].card_id,
            conclusion=None,
            decided_by_name=None,
            decided_at=None,
            inputs=inputs,
            reserved_to="engagement_partner",
            subject=subject,
            allowed_actions=[],
        )
    if decided:
        card = max(decided, key=lambda c: c.decided_at)
        names = await _names([card.decided_by])
        return GoingConcernOut(
            state="decided",
            decision_card_id=card.card_id,
            conclusion=_conclusion(card.option_key),
            decided_by_name=names.get(card.decided_by),
            decided_at=card.decided_at,
            inputs=inputs,
            reserved_to="engagement_partner",
            subject=subject,
            allowed_actions=[],
        )
    return GoingConcernOut(
        state="not_requested",
        decision_card_id=None,
        conclusion=None,
        decided_by_name=None,
        decided_at=None,
        inputs=inputs,
        reserved_to="engagement_partner",
        subject=subject,
        allowed_actions=actions,
    )


# --- AUD-18: the EQR review ----------------------------------------------------------------------

_REVIEW = text(
    "SELECT id, engagement_id, eqr_user_id, status, version FROM eqr_reviews "
    "WHERE work_item_id = :wi"
)
_CHECKLIST = text(
    "SELECT item_key, position, status, sub_line, updated_by, version FROM eqr_checklist_items "
    "WHERE eqr_review_id = :r ORDER BY position"
)
_CARDS = text(
    "SELECT id, source_kind, source_ref, title, snapshot, snapshot_sha256, citation_ids, "
    "reviewed_at, reviewed_by FROM eqr_digest_cards WHERE eqr_review_id = :r "
    "AND superseded_by IS NULL ORDER BY created_at, id"
)
_CONCURRENCE = text(
    "SELECT concurred_by, created_at, concurrence_date FROM eqr_concurrences "
    "WHERE eqr_review_id = :r ORDER BY created_at DESC LIMIT 1"
)


async def eqr_review(ctx: AuthContext, work_item_id: UUID) -> EqrReviewOut:
    async with tenant_session(ctx.tenant) as session:
        review = (await session.execute(_REVIEW, {"wi": work_item_id})).first()
        if review is None:
            raise NotFound(eqr_service.REVIEW_TARGET)
        checklist = (await session.execute(_CHECKLIST, {"r": review.id})).all()
        cards = (await session.execute(_CARDS, {"r": review.id})).all()
        concurrence = (await session.execute(_CONCURRENCE, {"r": review.id})).first()
    template = await eqr_service.checklist_wording(ctx.tenant, review.engagement_id)
    notes = [
        n
        for n in await note_states(
            ctx.tenant, review.engagement_id, eqr_service.REVIEW_TARGET, review.id
        )
        if n.status in _NOTE_STATUS
    ]
    names = await _names(
        [review.eqr_user_id]
        + [c.updated_by for c in checklist]
        + [c.reviewed_by for c in cards]
        + [n.assignee_user_id for n in notes]
        + ([] if concurrence is None else [concurrence.concurred_by])
    )
    viewer_is_eqr = ctx.tenant.actor_kind == "human" and ctx.user_id == review.eqr_user_id
    done = sum(1 for c in checklist if c.status == "done")
    open_notes = sum(1 for n in notes if n.status in ("open", "responded"))
    blockers: list[str] = []
    if done < len(checklist):
        blockers.append(f"checklist_open:{len(checklist) - done}")
    if open_notes:
        blockers.append(f"eqr_notes_open:{open_notes}")
    if not viewer_is_eqr:
        blockers.append("not_assigned_eqr")
    concurred = concurrence is not None or review.status == "concurred"
    status: Literal["in_progress", "ready_to_concur", "concurred"] = (
        "concurred"
        if concurred
        else "ready_to_concur"
        if done == len(checklist) and not open_notes
        else "in_progress"
    )
    # The contract says `review_note.create` where the matrix says `review_note.raise`.
    asked = [_MATRIX_NAME.get(a, a) for a in _EQR_ACTIONS]
    granted = set(await _held(ctx, work_item_id, asked))
    held: list[EqrAction] = [a for a in _EQR_ACTIONS if _MATRIX_NAME.get(a, a) in granted]
    if not viewer_is_eqr or concurred:
        held = [a for a in held if a not in _EQR_ONLY]
    if status != "ready_to_concur":
        held = [a for a in held if a != "eqr.concur"]
    return EqrReviewOut(
        work_item_id=work_item_id,
        required=True,
        eqr_name=names.get(review.eqr_user_id),
        status=status,
        checklist=[
            EqrChecklistItemOut(
                item_key=c.item_key,
                position=c.position,
                title=str(template.get(c.item_key) or c.item_key),
                status=c.status,
                sub_line=None if c.sub_line == template.get(c.item_key) else c.sub_line,
                updated_by_name=None if c.updated_by is None else names.get(c.updated_by),
                version=int(c.version),
            )
            for c in checklist
        ],
        checklist_done=done,
        checklist_total=len(checklist),
        digest_cards=[
            EqrDigestCardOut(
                id=c.id,
                source_kind=c.source_kind,
                source_ref=c.source_ref,
                title=c.title,
                rows=[
                    CompletionKvOut(label=str(r["label"]), value=str(r["value"]))
                    for r in cast("list[dict[str, object]]", c.snapshot or [])
                ],
                snapshot_sha256=c.snapshot_sha256,
                citation_ids=list(c.citation_ids or []),
                link_target="/audits/$auditId",
                reviewed_at=c.reviewed_at,
                reviewed_by_name=None if c.reviewed_by is None else names.get(c.reviewed_by),
            )
            for c in cards
        ],
        notes=[
            EqrNoteRowOut(
                id=n.id,
                ref=f"EQR-{position}",
                status=_NOTE_STATUS[n.status],
                assignee_name=None
                if n.assignee_user_id is None
                else names.get(n.assignee_user_id),
            )
            for position, n in enumerate(notes, start=1)
        ],
        concurrence=None
        if concurrence is None
        else EqrConcurrenceOut(
            concurred_by_name=names.get(concurrence.concurred_by, ""),
            concurred_at=concurrence.created_at,
            concurrence_date=concurrence.concurrence_date,
            not_involved_attested=True,
        ),
        blockers=[] if concurred else blockers,
        viewer_is_eqr=viewer_is_eqr,
        allowed_actions=held,
        version=int(review.version),
    )


# --- AUD-21: the representation letter -----------------------------------------------------------

_LETTER = text(
    "SELECT id, status, current_version_id, envelope_id, dated_as_of, signed_on, g7_met_at, "
    "version FROM representation_letters WHERE work_item_id = :wi"
)
_LETTER_VERSIONS = text(
    "SELECT v.id, v.version_no, v.template_version_id, v.representations, "
    "v.edited_paragraphs_sealed, v.sum_snapshot_id, v.content_hash, v.created_by, "
    "v.drafted_by_run_id, v.generated_document_id, v.created_at, a.approved_by, "
    "a.created_at AS approved_at FROM representation_letter_versions v "
    "LEFT JOIN LATERAL (SELECT approved_by, created_at FROM representation_letter_approvals "
    "WHERE version_id = v.id ORDER BY created_at DESC LIMIT 1) a ON true "
    "WHERE v.letter_id = :l ORDER BY v.version_no"
)


def _plain(blocks: object) -> str:
    """A clause's standard wording as text: its paragraphs' text runs (C11 content)."""
    parts: list[str] = []
    for block in cast("list[dict[str, object]]", blocks or []):
        runs = cast("list[dict[str, object]]", block.get("runs") or [])
        parts.append("".join(str(r.get("text", "")) for r in runs if r.get("type") == "text"))
    return "\n\n".join(p for p in parts if p)


def _version_out(v: object, names: dict[UUID, str]) -> RepresentationLetterVersionOut:
    row = cast("_LetterVersionRow", v)
    by = names.get(row.created_by, "")
    return RepresentationLetterVersionOut(
        version_no=row.version_no,
        content_hash=row.content_hash,
        created_by_name=f"{by} via Agent" if row.drafted_by_run_id is not None else by,
        created_at=row.created_at,
        approved_by_name=None if row.approved_by is None else names.get(row.approved_by),
        approved_at=row.approved_at,
        sum_snapshot_id=row.sum_snapshot_id,
        generated_document_id=row.generated_document_id,
    )


async def _letter_rows(
    tenant: TenantContext, work_item_id: UUID
) -> tuple[object, Sequence[object], dict[UUID, str]]:
    async with tenant_session(tenant) as session:
        letter = (await session.execute(_LETTER, {"wi": work_item_id})).first()
        if letter is None:
            raise NotFound("representation_letter")
        versions = list((await session.execute(_LETTER_VERSIONS, {"l": letter.id})).all())
    names = await _names(
        [cast("_LetterVersionRow", v).created_by for v in versions]
        + [cast("_LetterVersionRow", v).approved_by for v in versions]
    )
    return letter, versions, names


async def letter_versions(
    ctx: AuthContext, work_item_id: UUID
) -> list[RepresentationLetterVersionOut]:
    _letter, versions, names = await _letter_rows(ctx.tenant, work_item_id)
    return [_version_out(v, names) for v in versions]


async def representation_letter(
    ctx: AuthContext, work_item_id: UUID, version_no: int | None = None
) -> RepresentationLetterOut:
    letter, versions, names = await _letter_rows(ctx.tenant, work_item_id)
    row = cast("_LetterRow", letter)
    rows = [cast("_LetterVersionRow", v) for v in versions]
    if version_no is None:
        chosen = next((v for v in rows if v.id == row.current_version_id), None)
    else:
        chosen = next((v for v in rows if v.version_no == version_no), None)
        if chosen is None:
            raise NotFound("representation_letter_version")
    representations: list[LetterRepresentationOut] = []
    paragraphs: list[LetterParagraphOut] = []
    if chosen is not None:
        async with tenant_session(ctx.tenant) as session:
            parts = await report_template_parts(session, chosen.template_version_id)
            raw = None if parts is None else parts.clauses
        clauses = {str(c["clause_id"]): c for c in cast("list[dict[str, object]]", raw or [])}
        edits_text = await _unseal(
            ctx.tenant, chosen.edited_paragraphs_sealed, f"representation_letter:{row.id}"
        )
        edits = cast("dict[str, str]", json.loads(edits_text)) if edits_text else {}
        raw_reps: object = chosen.representations
        stored = cast(
            "list[dict[str, object]]",
            raw_reps if isinstance(raw_reps, list) else json.loads(str(raw_reps)),
        )
        for rep in stored:
            n = int(str(rep["n"]))
            clause = clauses.get(str(rep["clause_id"]), {})
            title = str(clause.get("title") or rep["clause_id"])
            included = bool(rep["included"])
            representations.append(
                LetterRepresentationOut(
                    key=str(rep["clause_id"]),
                    kind="specific",
                    paragraph_no=n,
                    title=title,
                    locked=False,
                    included=included,
                    trigger_ref=None,
                    firm_editable=True,
                    citations=[],
                )
            )
            if included:
                edited = edits.get(str(n))
                paragraphs.append(
                    LetterParagraphOut(
                        key=str(rep["clause_id"]),
                        number=n,
                        text=edited if edited is not None else _plain(clause.get("standard")),
                        human_edited=edited is not None,
                        citations=[],
                    )
                )
    final = row.status in ("approved", "sent", "signed", "date_mismatch")
    return RepresentationLetterOut(
        status=cast("RepresentationLetterStatus", row.status),
        current_version=None if chosen is None else _version_out(chosen, names),
        representations=representations,
        paragraphs=paragraphs,
        signers=[],
        report_date=await _report_date(ctx.tenant, work_item_id),
        dated_as_of=row.dated_as_of,
        signed_on=row.signed_on,
        g7_met=row.g7_met_at is not None,
        envelope_id=row.envelope_id,
        watermark="none" if final else "draft",
        allowed_actions=await _held(ctx, work_item_id, _LETTER_ACTIONS),
        version=int(row.version),
    )


type RepresentationLetterStatus = Literal[
    "drafting", "draft", "awaiting_partner_approval", "approved", "sent", "signed",
    "date_mismatch",
]  # fmt: skip


class _LetterRow:
    id: UUID
    status: str
    current_version_id: UUID | None
    envelope_id: UUID | None
    dated_as_of: date | None
    signed_on: date | None
    g7_met_at: object
    version: int


class _LetterVersionRow:
    id: UUID
    version_no: int
    template_version_id: UUID
    representations: object
    edited_paragraphs_sealed: bytes | None
    sum_snapshot_id: UUID | None
    content_hash: str
    created_by: UUID
    drafted_by_run_id: UUID | None
    generated_document_id: UUID | None
    created_at: datetime
    approved_by: UUID | None
    approved_at: datetime | None


__all__ = [
    "completion",
    "eqr_review",
    "going_concern",
    "legal_letter",
    "letter_versions",
    "representation_letter",
    "subsequent_events",
]
