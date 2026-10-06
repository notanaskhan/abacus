"""Engagement routes (SPEC-000 §8; TASK-008 design §3). Metadata only: content is served by the
content routes (request items), each with its own action (ADR-024)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified
from abacus.modules.engagements.service import (
    EngagementMetadata,
    EngagementSummary,
    NewEngagement,
    create_engagement,
    engagement_metadata,
    engagements_for,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, EngagementRole, current_context

router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])
Name = Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]


class EngagementIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Name
    client_name: Name
    client_entity_name: Name
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]

    @model_validator(mode="after")
    def _period(self) -> EngagementIn:
        if self.fiscal_period_end <= self.fiscal_period_start:
            raise ValueError("fiscal_period_end must be after fiscal_period_start")
        return self


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[EngagementRole, classified("internal")]


class EngagementSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Name
    type: Annotated[Literal["audit"], classified("internal")]
    status: Annotated[Literal["active", "archived"], classified("internal")]
    client_name: Name
    client_entity_name: Name
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


class EngagementOut(EngagementSummaryOut):
    team: Annotated[list[TeamMemberOut], classified("confidential")]


def _summary(summary: EngagementSummary) -> EngagementSummaryOut:
    e, names = summary.engagement, summary.names
    return EngagementSummaryOut(
        id=e.id,
        name=e.name,
        type="audit",
        status="archived" if e.status == "archived" else "active",
        client_name=names.client_name,
        client_entity_name=names.client_entity_name,
        fiscal_period_start=e.fiscal_period_start,
        fiscal_period_end=e.fiscal_period_end,
        created_at=e.created_at,
    )


def _out(metadata: EngagementMetadata) -> EngagementOut:
    summary = _summary(EngagementSummary(metadata.engagement, metadata.names))
    team = [
        TeamMemberOut(user_id=m.user_id, display_name=m.display_name, role=m.role)
        for m in metadata.team
    ]
    return EngagementOut(**summary.model_dump(), team=team)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.post("", action="engagement.create", response_model=EngagementOut, status_code=201)
async def create_engagement_route(body: EngagementIn, ctx: Ctx) -> EngagementOut:
    new = NewEngagement(
        name=body.name,
        client_name=body.client_name,
        client_entity_name=body.client_entity_name,
        fiscal_period_start=body.fiscal_period_start,
        fiscal_period_end=body.fiscal_period_end,
    )
    return _out(await create_engagement(ctx, new))


@router.get("", action="engagement.read_metadata", response_model=list[EngagementSummaryOut])
async def list_engagements_route(ctx: Ctx) -> list[EngagementSummaryOut]:
    return [_summary(s) for s in await engagements_for(ctx)]


@router.get("/{engagement_id}", action="engagement.read_metadata", response_model=EngagementOut)
async def get_engagement_route(engagement_id: UUID, ctx: Ctx) -> EngagementOut:
    return _out(await engagement_metadata(ctx, engagement_id))
