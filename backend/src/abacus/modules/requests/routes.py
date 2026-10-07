"""Request item routes (SPEC-000 §8; TASK-008 design §3). Content: members only (ADR-024)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
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
    request_items_for,
)

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
