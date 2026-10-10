"""Request item routes (SPEC-000 §8; TASK-008 design §3). Content: members only (ADR-024)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.requests.service import (
    AppliedMethodology,
    NewRequestItem,
    RequestItemView,
    add_request_item,
    apply_methodology,
    assign_to_client,
    import_request_list,
    list_due_date,
    preview_request_list,
    request_items_for,
    set_client_visibility,
    set_item_due_dates,
    set_list_due_date,
    set_tier,
)
from abacus.modules.requests.workbook import MAX_BYTES, Problem, RequestListInvalid

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/request-items", tags=["requests"])
Status = Literal["open", "received", "ready_for_review", "needs_revision"]
Tier = Literal["A", "B", "C", "D", "E"]
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
