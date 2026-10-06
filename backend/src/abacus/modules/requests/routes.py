"""Request item routes (SPEC-000 §8; TASK-008 design §3). Content: members only (ADR-024)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.service import NewRequestItem, add_request_item, request_items_for

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/request-items", tags=["requests"])
Status = Literal["open", "received", "ready_for_review", "needs_revision"]


class RequestItemIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    description: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
    audit_area: Annotated[str, Field(min_length=1, max_length=100), classified("confidential")]


class RequestItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    audit_area: Annotated[str, classified("confidential")]
    status: Annotated[Status, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


def _out(item: RequestItem) -> RequestItemOut:
    return RequestItemOut.model_validate(
        {
            "id": item.id,
            "engagement_id": item.engagement_id,
            "description": item.description,
            "audit_area": item.audit_area,
            "status": item.status,
            "created_at": item.created_at,
        }
    )


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
