"""TAX-03's intake read model (T-02-T18; T-02 §3.4; DV-6, DV-7; DEC-37; DEC-1470).

`GET /v1/tax-returns/{id}/intake` (`tax_return.read`) composes, for the return's work item:

- **The binder card**: the newest PBC binder (C5), who published it and when, whether the client
  marked it done, and the last upload.
- **Requests by category**: C5's Source Documents aggregate (`requests.source_documents`), so
  "5 of 7" and each band's "n of N" foot to one count; each row carries the file that answers it
  (name, channel, day) or its asking, and the version a person approves with **Approve Document**
  (DV-6: C5's `evidence.accept` on that version, the existing decision route; DEC-37's firm
  setting decides whether filing also accepts).
- **Waiting files**: N-01's inbox attachments waiting on the client, with code's flags. The
  wrong-year check is code (ADR-050): the attachment's classified tax year against the return's
  ("2024 ≠ 2025"), or N-01's own `wrong_year` flag. "Ignore · wrong year" is N-01's ignore with
  reason `wrong_tax_year`.
- **Suggestions** (DV-7, C19 fail closed): the matcher's stored proposals are shown only when
  the taxpayer's consent set (`use` and `ai_disclosure`, the return's year) is in force, the firm
  opted in to client data, and the matcher is live for the firm. Otherwise the dock draws the
  DF-04 line and says why (`consent_missing` or `agents_off`). Reading never calls a model: the
  proposals were made (or refused) when the file arrived, by the matcher's own gate.
- **Questions**: each questionnaire's counts and submission, never its answers (POR-05's drawer
  reads those under `questionnaire.read`).
- **K-1 hand-offs**: T-02-T20's hand-offs to this return (DEC-88: the source only for a reader
  of both returns).

Client service (Grace, DEC-20) sees request status and file names, never extracted values: the
tax year and the suggestions are left out for that role (`suggestions = "hidden"`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from abacus.kernel._statuses import K1HandoffStatus
from abacus.kernel.clock import now
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import MATCHER, stage_for
from abacus.modules.communications.api import WaitingAttachment, card_candidates
from abacus.modules.communications.api import waiting_for_client as inbox_waiting_for
from abacus.modules.evidence.api import PendingDuplicate, attachment_tax_years, pending_duplicates
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    ai_client_data_opted_in,
    allowed_actions,
    authorise,
    engagement_role_of,
    names_of,
)
from abacus.modules.organisations.api import tri_consent_verdict
from abacus.modules.requests.api import (
    BinderCard,
    SourceDocumentGroup,
    SourceDocumentRow,
    SourceDocuments,
    binder_card,
    source_documents,
    work_item_questionnaires,
)
from abacus.modules.tax import k1_packages
from abacus.modules.tax.overview import Loaded, load_return, return_resource
from abacus.modules.tax.returns_contract import (
    IntakeBinderOut,
    IntakeCategoryOut,
    IntakeDuplicateOut,
    IntakeQuestionnaireOut,
    IntakeRequestOut,
    IntakeSuggestionOut,
    IntakeWaitingFileOut,
    K1DependencyOut,
    SuggestionsState,
    TaxReturnIntakeOut,
)

CONTENT: Final = "tax_return.read"
# What a person may do from TAX-03 (each its owner's route; nothing here acts).
ACTIONS: Final = (
    "evidence.accept",  # Approve Document (DV-6)
    "inbox.file",  # File to request
    "inbox.triage",  # Not this…, Ignore · reason
    "request_item.create",  # Request more…
    "questionnaire.ask",  # Ask the client…
)
_CLIENT_SERVICE: Final = "client_service"


def _key(category_id: UUID | None, label: str) -> str:
    return str(category_id) if category_id is not None else label.lower().replace(" ", "_")


def _row(
    g: SourceDocumentGroup, r: SourceDocumentRow, repeats: dict[UUID, PendingDuplicate]
) -> IntakeRequestOut:
    upload = r.latest_upload
    dup = repeats.get(upload.evidence_version_id) if upload is not None else None
    return IntakeRequestOut(
        id=r.request_item_id,
        binder_id=r.binder_id,
        category=_key(g.category_id, g.label),
        title=r.title,
        status=r.status,
        overdue=r.overdue,
        requested_at=r.requested_at,
        due_on=r.due_on,
        latest_version_id=(
            None
            if upload is None
            else dup.original_version_id
            if dup is not None
            else upload.evidence_version_id
        ),
        file_name=(
            None
            if upload is None
            else dup.original_file_name
            if dup is not None
            else upload.path_label
        ),
        uploaded_on=upload.uploaded_on if upload else None,
        channel=upload.uploader_kind if upload else None,
        linked_count=r.linked_count,
        owed_by=r.owed_by.display if r.owed_by else None,
        duplicate=None
        if dup is None
        else IntakeDuplicateOut(version_id=dup.version_id, file_name=dup.file_name),
    )


async def _requests(
    ctx: AuthContext, work_item_id: UUID
) -> tuple[list[IntakeCategoryOut], list[IntakeRequestOut], int, int]:
    try:
        found: SourceDocuments = await source_documents(ctx, work_item_id)
    except (Forbidden, NotFound):
        return [], [], 0, 0
    categories = [
        IntakeCategoryOut(
            key=_key(g.category_id, g.label),
            requested=g.total,
            received=g.received,
            label=g.label,
        )
        for g in found.groups
    ]
    latest = [
        r.latest_upload.evidence_version_id
        for g in found.groups
        for r in g.rows
        if r.latest_upload
    ]
    # TAX-03 e: a flagged repeat shows under the copy it repeats, which the row keeps naming.
    repeats = await pending_duplicates(ctx.tenant, latest) if latest else {}
    rows = [_row(g, r, repeats) for g in found.groups for r in g.rows]
    return categories, rows, found.total, found.received


async def _binder(card: BinderCard | None) -> IntakeBinderOut | None:
    if card is None:
        return None
    people = [u for u in (card.published_by, card.marked_done_by) if u is not None]
    names = await names_of(people) if people else {}
    return IntakeBinderOut(
        id=card.id,
        name=card.name,
        status=card.status,
        published_at=card.published_at,
        published_by_name=names.get(card.published_by) if card.published_by else None,
        marked_done_at=card.marked_done_at,
        marked_done_by_name=names.get(card.marked_done_by) if card.marked_done_by else None,
        last_upload_at=card.last_upload_at,
    )


async def suggestions_state(ctx: AuthContext, loaded: Loaded, extracted: bool) -> SuggestionsState:
    """DV-7: whether the matcher's proposals may be shown on this return now (fail closed)."""
    if not extracted:
        return "hidden"
    verdict = await tri_consent_verdict(
        ctx.tenant,
        [loaded.client_entity_id],
        await now(ctx.tenant),
        tax_year=loaded.row.tax_year,
    )
    if not verdict.valid:
        return "consent_missing"
    if not await ai_client_data_opted_in(ctx.tenant):
        return "agents_off"
    if await stage_for(ctx.tenant, MATCHER) != "live":
        return "agents_off"
    return "shown"


async def _waiting(
    ctx: AuthContext,
    loaded: Loaded,
    files: Sequence[WaitingAttachment],
    *,
    extracted: bool,
    state: SuggestionsState,
    open_requests: set[UUID],
) -> list[IntakeWaitingFileOut]:
    ids = [f.id for f in files]
    years = await attachment_tax_years(ctx.tenant, ids) if extracted and ids else {}
    proposed = await card_candidates(ctx, ids) if state == "shown" and ids else {}
    out: list[IntakeWaitingFileOut] = []
    for f in files:
        kinds = sorted({flag.kind for flag in f.flags})
        year = years.get(f.id)
        wrong = "wrong_year" in kinds or (year is not None and year != loaded.row.tax_year)
        top = next(
            (c for c in proposed.get(f.id, []) if c.kind == "request" and c.id in open_requests),
            None,
        )
        out.append(
            IntakeWaitingFileOut(
                attachment_id=f.id,
                thread_id=f.thread_id,
                message_id=f.message_id,
                file_name=f.file_name,
                media_type=f.media_type,
                size_bytes=f.size_bytes,
                channel=f.channel,
                sender=f.sender_display,
                subject=f.subject_display,
                received_at=f.received_at,
                tax_year=year if extracted else None,
                wrong_year=wrong,
                duplicate="duplicate_hash" in kinds,
                flags=kinds,
                # A wrong-year file is ignored, never filed to this year's request.
                suggestion=None
                if top is None or wrong
                else IntakeSuggestionOut(
                    request_id=top.id,
                    label=top.label,
                    confidence=round(top.confidence * 100),
                ),
            )
        )
    return out


async def intake(ctx: AuthContext, return_id: UUID) -> TaxReturnIntakeOut:
    """`GET /v1/tax-returns/{id}/intake`."""
    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, CONTENT, resource)
    may = await allowed_actions(ctx, resource, ACTIONS)
    role = await engagement_role_of(ctx.tenant, loaded.facts.engagement_id, ctx.user_id)
    extracted = role != _CLIENT_SERVICE
    categories, requests, total, received = await _requests(ctx, return_id)
    card = await _binder(await binder_card(ctx, return_id))
    files = await inbox_waiting_for(ctx.tenant, loaded.facts.client_id)
    state = (
        await suggestions_state(ctx, loaded, extracted)
        if files
        else ("hidden" if not extracted else "agents_off")
    )
    open_requests = {r.id for r in requests if r.status in ("requested", "returned")}
    waiting = await _waiting(
        ctx, loaded, files, extracted=extracted, state=state, open_requests=open_requests
    )
    try:
        asked = await work_item_questionnaires(ctx, loaded.facts.engagement_id, return_id)
    except (Forbidden, NotFound):
        asked = []
    submitters = [q.submitted_by for q in asked if q.submitted_by is not None]
    names = await names_of(submitters) if submitters else {}
    return TaxReturnIntakeOut(
        return_id=return_id,
        binder_id=card.id if card else None,
        categories=categories,
        waiting_files=len(waiting),
        questionnaire_ids=[q.id for q in asked],
        k1_handoffs=[  # T-02-T20's hand-offs, the source link per DEC-88
            K1DependencyOut(
                source_return_id=d.source_return_id,
                issuer_name=d.issuer_name,
                status=K1HandoffStatus(d.status),
                blocking=d.blocking,
            )
            for d in await k1_packages.dependencies(ctx, return_id)
        ],
        tax_year=loaded.row.tax_year,
        binder=card,
        requests_total=total,
        requests_received=received,
        requests=requests,
        waiting=waiting,
        suggestions=state,
        questionnaires=[
            IntakeQuestionnaireOut(
                id=q.id,
                kind=q.kind,
                title=q.title,
                status=q.status,
                answered=q.answered,
                total=q.total,
                submitted_at=q.submitted_at,
                submitted_by_name=names.get(q.submitted_by) if q.submitted_by else None,
            )
            for q in asked
        ],
        allowed_actions=sorted(may),
    )


__all__ = ["ACTIONS", "intake", "suggestions_state"]
