"""Request item routes (SPEC-000 §8; TASK-008 design §3). Content: members only (ADR-024)."""

from __future__ import annotations

from datetime import datetime
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
    import_request_list,
    preview_request_list,
    request_items_for,
)
from abacus.modules.requests.workbook import MAX_BYTES, Problem, RequestListInvalid

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/request-items", tags=["requests"])
Status = Literal["open", "received", "ready_for_review", "needs_revision"]
Tier = Literal["A", "B", "C", "D", "E"]


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
