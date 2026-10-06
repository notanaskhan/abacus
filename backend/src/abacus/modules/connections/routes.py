"""Retrieval routes (SPEC-000 §8; TASK-010 design §7, Q4). PROTECTED."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, model_validator

from abacus.kernel.classification import classified
from abacus.modules.connections.connector import Period
from abacus.modules.connections.retrievals import (
    RetrievalView,
    retrieval_status,
    trigger_retrieval,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/retrievals", tags=["retrievals"])
Status = Literal["running", "succeeded", "failed_validation", "failed"]


class RetrievalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_item_id: Annotated[UUID, classified("internal")]
    period_start: Annotated[date, classified("confidential")]
    period_end: Annotated[date, classified("confidential")]

    @model_validator(mode="after")
    def _period(self) -> RetrievalIn:
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be before period_start")
        return self


class RetrievalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sync_run_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    status: Annotated[Status, classified("internal")]
    failure_code: Annotated[str | None, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]


def _out(view: RetrievalView) -> RetrievalOut:
    return RetrievalOut.model_validate(view, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.post("", action="evidence.upload", response_model=RetrievalOut, status_code=202)
async def start_retrieval_route(engagement_id: UUID, body: RetrievalIn, ctx: Ctx) -> RetrievalOut:
    view = await trigger_retrieval(
        ctx,
        engagement_id=engagement_id,
        request_item_id=body.request_item_id,
        period=Period(body.period_start, body.period_end),
    )
    return _out(view)


@router.get("/{sync_run_id}", action="request_item.read", response_model=RetrievalOut)
async def get_retrieval_route(engagement_id: UUID, sync_run_id: UUID, ctx: Ctx) -> RetrievalOut:
    return _out(await retrieval_status(ctx, engagement_id=engagement_id, run_id=sync_run_id))
