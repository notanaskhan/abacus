"""Request item routes (SPEC-000 §8; TASK-008 design §3). Content: members only (ADR-024)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity.api import (
    OWN,
    AbacusRouter,
    AuthContext,
    current_context,
    current_member,
)
from abacus.modules.requests.client_responses import (
    ClientResponse,
    list_done,
    mark_done,
    respond,
    responses,
)
from abacus.modules.requests.comments import (
    MAX_BODY,
    MAX_REASON,
    CommentView,
    mark_read,
    mention_candidates,
    post_comment,
    redact,
    thread,
)
from abacus.modules.requests.service import (
    AppliedMethodology,
    GuidanceEdit,
    NewRequestItem,
    RequestItemView,
    add_request_item,
    apply_methodology,
    assign_to_client,
    import_request_list,
    list_due_date,
    overdue_mine,
    preview_request_list,
    request_items_for,
    search_request_items,
    set_client_visibility,
    set_item_document_kind,
    set_item_due_dates,
    set_item_guidance,
    set_list_due_date,
    set_tier,
    your_part,
)
from abacus.modules.requests.workbook import MAX_BYTES, Problem, RequestListInvalid

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/request-items", tags=["requests"])
Effort = Literal["small", "medium", "large"]
Status = Literal["open", "received", "ready_for_review", "needs_revision"]
Tier = Literal["A", "B", "C", "D", "E"]
DocumentKind = Literal["bank_statement", "ar_aging", "ap_aging", "schedule"]
TierSource = Literal["override", "methodology", "rule"]


class RequestItemIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    description: Annotated[
        MultiLineText, Field(min_length=1, max_length=2000), classified("confidential")
    ]
    audit_area: Annotated[
        SingleLineText, Field(min_length=1, max_length=100), classified("confidential")
    ]


class RequestItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    audit_area: Annotated[str, classified("confidential")]
    status: Annotated[Status, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    retrievability_tier: Annotated[Tier | None, classified("internal")] = None
    client_visible: Annotated[bool, classified("internal")] = True
    client_assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    dataset: Annotated[str | None, classified("internal")] = None
    tier_source: Annotated[
        Literal["override", "methodology", "rule"] | None, classified("internal")
    ] = None
    available: Annotated[bool, classified("internal")] = False
    due_on: Annotated[date | None, classified("internal")] = None  # SPEC-027: its own
    # SPEC-029 (TASK-055): the document it expects, and who set it.
    document_kind: Annotated[DocumentKind | None, classified("internal")] = None
    document_kind_source: Annotated[Literal["rule", "override"] | None, classified("internal")] = (
        None
    )
    # SPEC-031 (TASK-060): the firm's, the template's or fixed copy; never a model's (ADR-111).
    why: Annotated[str | None, classified("confidential")] = None
    good_looks_like: Annotated[str | None, classified("confidential")] = None
    still_needed: Annotated[str | None, classified("confidential")] = None
    blocks_fieldwork: Annotated[bool, classified("internal")] = False
    effort: Annotated[Effort | None, classified("internal")] = None
    guidance_approved_by: Annotated[UUID | None, classified("internal")] = None  # SPEC-035
    comment_count: Annotated[int, classified("internal")] = 0  # SPEC-032 (TASK-062)
    unread_comments: Annotated[bool, classified("internal")] = False
    guidance_source: Annotated[
        Literal["template", "kind_default", "firm", "drafted"] | None, classified("internal")
    ] = None


def _out(item: RequestItemView) -> RequestItemOut:
    # Validation, not coercion: an unexpected status from the database is an error, not hidden.
    return RequestItemOut.model_validate(item, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.post("", action="request_item.create", response_model=RequestItemOut, status_code=201)
async def create_request_item_route(
    engagement_id: UUID, body: RequestItemIn, ctx: Ctx
) -> RequestItemOut:
    new = NewRequestItem(description=body.description, audit_area=body.audit_area)
    return _out(await add_request_item(ctx, engagement_id, new))


@router.get("", action="request_item.read", response_model=list[RequestItemOut])
async def list_request_items_route(engagement_id: UUID, ctx: Ctx) -> list[RequestItemOut]:
    return [_out(item) for item in await request_items_for(ctx, engagement_id)]


class ClientVisibilityIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_visible: Annotated[bool, classified("internal")]


class ClientAssigneeIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID | None, classified("internal")]


@router.put(
    "/{item_id}/client-visibility", action="request_item.update", response_model=RequestItemOut
)
async def set_client_visibility_route(
    engagement_id: UUID, item_id: UUID, body: ClientVisibilityIn, ctx: Ctx
) -> RequestItemOut:
    """SPEC-020 (TASK-035 D3): show or hide the item from client users."""
    view = await set_client_visibility(
        ctx, engagement_id, item_id, client_visible=body.client_visible
    )
    return _out(view)


@router.put(
    "/{item_id}/client-assignee",
    action="request_item.assign",
    response_model=RequestItemOut,
    errors=(409,),
)
async def assign_to_client_route(
    engagement_id: UUID, item_id: UUID, body: ClientAssigneeIn, ctx: Ctx
) -> RequestItemOut:
    """SPEC-020 (TASK-035 D4): assign the item to a client contributor, or clear it."""
    return _out(await assign_to_client(ctx, engagement_id, item_id, user_id=body.user_id))


class DueDatesIn(BaseModel):
    """SPEC-027 AC-9 (TASK-051): set or clear (`null`) several items' due date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_ids: Annotated[list[UUID], Field(min_length=1, max_length=2000), classified("internal")]
    due_on: Annotated[date | None, classified("internal")]


class DefaultDueDate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    due_on: Annotated[date | None, classified("internal")]


@router.put("/due-dates", action="request_item.update", response_model=list[RequestItemOut])
async def due_dates_route(engagement_id: UUID, body: DueDatesIn, ctx: Ctx) -> list[RequestItemOut]:
    return [
        _out(i) for i in await set_item_due_dates(ctx, engagement_id, body.item_ids, body.due_on)
    ]


@router.get("/default-due-date", action="request_item.read", response_model=DefaultDueDate)
async def default_due_date_route(engagement_id: UUID, ctx: Ctx) -> DefaultDueDate:
    """The date an item without its own is due."""
    return DefaultDueDate(due_on=await list_due_date(ctx, engagement_id))


@router.put("/default-due-date", action="request_item.update", response_model=DefaultDueDate)
async def set_default_due_date_route(
    engagement_id: UUID, body: DefaultDueDate, ctx: Ctx
) -> DefaultDueDate:
    await set_list_due_date(ctx, engagement_id, body.due_on)
    return DefaultDueDate(due_on=body.due_on)


class TierIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # None clears the override: the firm's rules classify the item again.
    tier: Annotated[Tier | None, classified("internal")]


class DocumentKindIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # None with `clear` false: "no particular document". `clear`: the rules apply again.
    document_kind: Annotated[DocumentKind | None, classified("internal")] = None
    clear: Annotated[bool, classified("internal")] = False


@router.put(
    "/{item_id}/document-kind", action="request_item.update", response_model=RequestItemOut
)
async def set_document_kind_route(
    engagement_id: UUID, item_id: UUID, body: DocumentKindIn, ctx: Ctx
) -> RequestItemOut:
    """SPEC-029 AC-5: set the document the item expects, or return it to the rules."""
    return _out(
        await set_item_document_kind(
            ctx, engagement_id, item_id, kind=body.document_kind, clear=body.clear
        )
    )


class GuidanceIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    why: Annotated[MultiLineText | None, Field(max_length=1000), classified("confidential")] = None
    good_looks_like: Annotated[
        MultiLineText | None, Field(max_length=1000), classified("confidential")
    ] = None
    still_needed: Annotated[
        MultiLineText | None, Field(max_length=1000), classified("confidential")
    ] = None
    blocks_fieldwork: Annotated[bool, classified("internal")] = False
    effort: Annotated[Effort | None, classified("internal")] = None


@router.put("/{item_id}/guidance", action="request_item.update", response_model=RequestItemOut)
async def set_guidance_route(
    engagement_id: UUID, item_id: UUID, body: GuidanceIn, ctx: Ctx
) -> RequestItemOut:
    """SPEC-031 AC-3: the firm writes why, what good looks like and the still-needed note, and
    plans the item (blocks fieldwork, effort)."""
    edit = GuidanceEdit(
        body.why, body.good_looks_like, body.still_needed, body.blocks_fieldwork, body.effort
    )
    return _out(await set_item_guidance(ctx, engagement_id, item_id, edit))


class YourPartOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items_left: Annotated[int, classified("internal")]
    blocks_fieldwork: Annotated[int, classified("internal")]
    minutes: Annotated[int, classified("internal")]


@router.get("/your-part", action="request_item.read", response_model=YourPartOut)
async def your_part_route(engagement_id: UUID, ctx: Ctx) -> YourPartOut:
    """SPEC-031 AC-6: what's left for this client user on the engagement."""
    part = await your_part(ctx, engagement_id)
    return YourPartOut(
        items_left=part.items_left, blocks_fieldwork=part.blocks_fieldwork, minutes=part.minutes
    )


@router.put("/{item_id}/tier", action="request_item.update", response_model=RequestItemOut)
async def set_tier_route(
    engagement_id: UUID, item_id: UUID, body: TierIn, ctx: Ctx
) -> RequestItemOut:
    """SPEC-022 AC-2: override the item's tier, or clear the override."""
    return _out(await set_tier(ctx, engagement_id, item_id, tier=body.tier))


# Applying a methodology version to the engagement (SPEC-008 §8; TASK-023 D2).
methodology_router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/methodology", tags=["methodology"]
)


class ApplyMethodologyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version_id: Annotated[UUID, classified("internal")]


class AppliedMethodologyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    items_created: Annotated[int, classified("internal")]


@methodology_router.post(
    "",
    action="engagement.apply_methodology",
    response_model=AppliedMethodologyOut,
    status_code=201,
    errors=(409,),
)
async def apply_methodology_route(
    engagement_id: UUID, body: ApplyMethodologyIn, ctx: Ctx
) -> AppliedMethodologyOut:
    applied: AppliedMethodology = await apply_methodology(ctx, engagement_id, body.version_id)
    return AppliedMethodologyOut(
        version_id=applied.version_id, items_created=applied.items_created
    )


# --- Request list import (SPEC-018 §8) ----------------------------------------------------------


class SheetPreviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    headers: Annotated[list[str], classified("confidential")]
    rows: Annotated[list[list[str]], classified("confidential")]
    suggested_description: Annotated[int | None, classified("internal")]
    suggested_area: Annotated[int | None, classified("internal")]
    suggested_tier: Annotated[int | None, classified("internal")]


class ImportCountsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: Annotated[int, classified("internal")]
    duplicates: Annotated[int, classified("internal")]
    empty: Annotated[int, classified("internal")]
    unmatched_areas: Annotated[int, classified("internal")]


async def _workbook(request: Request) -> bytes:
    """The raw `.xlsx` body (SPEC-008 D3), refused past the limit before it is all read."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_BYTES:
            raise RequestListInvalid([Problem(None, None, None, "too_large")])
    return bytes(data)


def _invalid(error: RequestListInvalid) -> RequestValidationError:
    """Where and what, never the cell (ADR-052), in the validation error shape."""
    return RequestValidationError(
        [
            {
                "loc": ("body", *(p for p in (e.sheet, e.row, e.column) if p is not None)),
                "msg": e.code,
                "type": e.code,
            }
            for e in error.problems
        ]
    )


@router.post("/import/preview", action="request_item.create", response_model=list[SheetPreviewOut])
async def preview_import_route(
    engagement_id: UUID,
    request: Request,
    ctx: Ctx,
    header_row: Annotated[int, Query(ge=1, le=50)] = 1,
) -> list[SheetPreviewOut]:
    try:
        sheets = await preview_request_list(
            ctx, engagement_id, await _workbook(request), header_row
        )
    except RequestListInvalid as error:
        raise _invalid(error) from None
    return [
        SheetPreviewOut(
            name=s.name,
            headers=list(s.headers),
            rows=[list(r) for r in s.rows],
            suggested_description=s.suggested_description,
            suggested_area=s.suggested_area,
            suggested_tier=s.suggested_tier,
        )
        for s in sheets
    ]


@router.post(
    "/import", action="request_item.create", response_model=ImportCountsOut, status_code=201
)
async def import_route(
    engagement_id: UUID,
    request: Request,
    ctx: Ctx,
    sheet: Annotated[str, Query(min_length=1, max_length=100)],
    description: Annotated[int, Query(ge=0, le=200)],
    area: Annotated[int, Query(ge=0, le=200)],
    header_row: Annotated[int, Query(ge=1, le=50)] = 1,
    tier: Annotated[int | None, Query(ge=0, le=200)] = None,
) -> ImportCountsOut:
    try:
        counts = await import_request_list(
            ctx,
            engagement_id,
            await _workbook(request),
            sheet=sheet,
            header_row=header_row,
            description=description,
            area=area,
            tier=tier,
        )
    except RequestListInvalid as error:
        raise _invalid(error) from None
    return ImportCountsOut(
        created=counts.created,
        duplicates=counts.duplicates,
        empty=counts.empty,
        unmatched_areas=counts.unmatched_areas,
    )


# --- Comments (SPEC-032; TASK-062; ADR-109) ------------------------------------------------------


class CommentIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=MAX_BODY), classified("restricted")]
    share: Annotated[bool, classified("internal")] = False  # firm only; a client's is shared
    corrects: Annotated[UUID | None, classified("internal")] = None
    mentions: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []


class RedactionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    redacted_by_name: Annotated[str, classified("confidential")]
    redacted_at: Annotated[datetime, classified("internal")]
    reason: Annotated[str, classified("confidential")]


class CommentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    author_user_id: Annotated[UUID, classified("internal")]
    author_name: Annotated[str, classified("confidential")]
    author_side: Annotated[Literal["firm", "client"], classified("internal")]
    visibility: Annotated[Literal["internal", "shared"], classified("internal")]
    text: Annotated[str | None, classified("restricted")] = None
    created_at: Annotated[datetime, classified("internal")]
    corrects: Annotated[UUID | None, classified("internal")] = None
    corrected_by: Annotated[list[UUID], classified("internal")] = []
    mentions: Annotated[list[UUID], classified("internal")] = []
    redaction: Annotated[RedactionOut | None, classified("confidential")] = None


def _comment_out(view: CommentView) -> CommentOut:
    return CommentOut.model_validate(view, from_attributes=True)


class MentionCandidateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    side: Annotated[Literal["firm", "client"], classified("internal")]


class ThreadReadIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID | None, classified("internal")] = None


class RedactIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=MAX_REASON), classified("confidential")]


class ThreadReadOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    read: Annotated[bool, classified("internal")] = True


@router.get(
    "/{item_id}/comments/mention-candidates",
    action="comment.create",
    response_model=list[MentionCandidateOut],
)
async def mention_candidates_route(
    engagement_id: UUID,
    item_id: UUID,
    ctx: Ctx,
    visibility: Annotated[Literal["internal", "shared"], Query()] = "internal",
) -> list[MentionCandidateOut]:
    """SPEC-032 AC-5: who may be mentioned, as they may read the comment."""
    found = await mention_candidates(ctx, engagement_id, item_id, visibility)
    return [MentionCandidateOut.model_validate(c, from_attributes=True) for c in found]


@router.get("/{item_id}/comments", action="comment.read", response_model=list[CommentOut])
async def item_comments_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> list[CommentOut]:
    """SPEC-032 AC-1, AC-3: the item's own thread."""
    return [_comment_out(c) for c in await thread(ctx, engagement_id, item_id, None)]


@router.post(
    "/{item_id}/comments", action="comment.create", response_model=CommentOut, status_code=201
)
async def post_item_comment_route(
    engagement_id: UUID, item_id: UUID, body: CommentIn, ctx: Ctx
) -> CommentOut:
    """SPEC-032 AC-2, AC-4, AC-5, AC-7."""
    return _comment_out(
        await post_comment(
            ctx,
            engagement_id,
            item_id,
            None,
            text=body.text,
            share=body.share,
            corrects=body.corrects,
            mentions=body.mentions,
        )
    )


@router.get(
    "/{item_id}/versions/{version_id}/comments",
    action="comment.read",
    response_model=list[CommentOut],
)
async def version_comments_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, ctx: Ctx
) -> list[CommentOut]:
    """SPEC-032 AC-1: one evidence version's thread."""
    return [_comment_out(c) for c in await thread(ctx, engagement_id, item_id, version_id)]


@router.post(
    "/{item_id}/versions/{version_id}/comments",
    action="comment.create",
    response_model=CommentOut,
    status_code=201,
)
async def post_version_comment_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, body: CommentIn, ctx: Ctx
) -> CommentOut:
    return _comment_out(
        await post_comment(
            ctx,
            engagement_id,
            item_id,
            version_id,
            text=body.text,
            share=body.share,
            corrects=body.corrects,
            mentions=body.mentions,
        )
    )


@router.post("/{item_id}/comments/read", action="comment.read", response_model=ThreadReadOut)
async def read_comments_route(
    engagement_id: UUID, item_id: UUID, body: ThreadReadIn, ctx: Ctx
) -> ThreadReadOut:
    """SPEC-032 Q6: the caller has read the thread (the item's, or a version's) up to now."""
    await mark_read(ctx, engagement_id, item_id, body.evidence_version_id)
    return ThreadReadOut()


@router.post(
    "/{item_id}/comments/{comment_id}/redact",
    action="comment.redact",
    response_model=ThreadReadOut,
    status_code=201,
)
async def redact_comment_route(
    engagement_id: UUID, item_id: UUID, comment_id: UUID, body: RedactIn, ctx: Ctx
) -> ThreadReadOut:
    """SPEC-032 AC-6: a firm administrator hides a comment posted in error."""
    await redact(ctx, engagement_id, item_id, comment_id, body.reason)
    return ThreadReadOut()


# --- The client's responses (SPEC-042; TASK-106) ------------------------------------------------


class ClientResponseOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    reason: Annotated[
        Literal["not_this_year", "sent_another_way", "dont_have"], classified("internal")
    ]
    note: Annotated[str | None, classified("confidential")]
    by: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


def _response_out(r: ClientResponse) -> ClientResponseOut:
    return ClientResponseOut.model_validate(asdict(r))


@router.get(
    "/client-responses", action="request_item.read", response_model=list[ClientResponseOut]
)
async def client_responses_route(engagement_id: UUID, ctx: Ctx) -> list[ClientResponseOut]:
    """SPEC-042 AC-3: the requests a client says don't apply."""
    return [_response_out(r) for r in await responses(ctx, engagement_id)]


class ClientResponseIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[
        Literal["not_this_year", "sent_another_way", "dont_have"], classified("internal")
    ]
    note: Annotated[str | None, Field(default=None, max_length=500), classified("confidential")]


class RespondedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]


@router.post(
    "/{item_id}/client-response",
    action="client_item.respond",
    response_model=RespondedOut,
    status_code=201,
)
async def client_respond_route(
    engagement_id: UUID, item_id: UUID, body: ClientResponseIn, ctx: Ctx
) -> RespondedOut:
    """SPEC-042 AC-1: the client says this doesn't apply, with a reason."""
    await respond(ctx, engagement_id, item_id, body.reason, body.note)
    return RespondedOut(request_item_id=item_id)


@router.post(
    "/{item_id}/client-response/withdraw",
    action="client_item.respond",
    response_model=RespondedOut,
    status_code=201,
)
async def client_withdraw_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> RespondedOut:
    """SPEC-042 AC-2: the client takes it back."""
    await respond(ctx, engagement_id, item_id, None, None)
    return RespondedOut(request_item_id=item_id)


class ListDoneOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    by: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


@router.get("/client-done", action="request_item.read", response_model=ListDoneOut | None)
async def client_done_route(engagement_id: UUID, ctx: Ctx) -> ListDoneOut | None:
    """SPEC-042 AC-4: who marked the list done."""
    found = await list_done(ctx, engagement_id)
    return ListDoneOut.model_validate(asdict(found)) if found is not None else None


@router.post(
    "/client-done",
    action="client_list.mark_done",
    response_model=ListDoneOut | None,
    status_code=201,
    errors=(409,),
)
async def mark_done_route(engagement_id: UUID, ctx: Ctx) -> ListDoneOut | None:
    """SPEC-042 AC-4: the client admin marks the list done."""
    await mark_done(ctx, engagement_id)
    found = await list_done(ctx, engagement_id)
    return ListDoneOut.model_validate(asdict(found)) if found is not None else None


# --- TASK-102: client items past due on the caller's engagements --------------------------------

firm_router = AbacusRouter(prefix="/v1/firm", tags=["requests"])


class OverdueCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    count: Annotated[int, classified("internal")]


@firm_router.get("/waiting/overdue", action=OWN, response_model=list[OverdueCountOut])
async def overdue_waiting_route(
    ctx: Annotated[AuthContext, Depends(current_member)],
) -> list[OverdueCountOut]:
    """Client items past due, per engagement on the caller's team."""
    return [
        OverdueCountOut(engagement_id=e, count=n) for e, n in await overdue_mine(ctx, date.today())
    ]


class ItemHitOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    audit_area: Annotated[str, classified("internal")]
    status: Annotated[str, classified("internal")]


@firm_router.get("/search/request-items", action=OWN, response_model=list[ItemHitOut])
async def search_request_items_route(
    ctx: Annotated[AuthContext, Depends(current_member)],
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[ItemHitOut]:
    """SPEC-302 AC-2: the command palette's request items, newest first."""
    return [
        ItemHitOut(
            id=i.id,
            engagement_id=i.engagement_id,
            description=i.description,
            audit_area=i.audit_area,
            status=i.status,
        )
        for i in await search_request_items(ctx, q)
    ]
