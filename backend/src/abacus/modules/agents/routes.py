"""Agent routes (SPEC-000 §8; TASK-012 Q1): screening results for the evidence board. Read-only:
agents propose, and nothing here lets anyone act on a proposal (ADR-005)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.service import ScreeningResultView, screening_results_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/screening-results", tags=["agents"])
Action = Literal["ready_for_review", "needs_revision"]
Reason = Literal["cell_not_found", "quote_mismatch", "value_mismatch"]


class CitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    quote: Annotated[str | None, classified("confidential")]
    value: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[Reason | None, classified("internal")]


class ScreeningResultOut(BaseModel):
    """Model text (`rationale`, `quote`, `unverified`) is untrusted: render as plain text."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    action: Annotated[Action, classified("internal")]
    confidence: Annotated[Decimal, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    citations: Annotated[list[CitationOut], classified("confidential")]
    unverified: Annotated[list[str], classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


def _out(result: ScreeningResultView) -> ScreeningResultOut:
    return ScreeningResultOut.model_validate(result, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.get("", action="evidence.read", response_model=list[ScreeningResultOut])
async def list_screening_results_route(engagement_id: UUID, ctx: Ctx) -> list[ScreeningResultOut]:
    return [_out(r) for r in await screening_results_for(ctx, engagement_id)]


# --- The engagement graph (SPEC-008 §8; TASK-023 D1) --------------------------------------------

graph_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/graph", tags=["agents"])


class GraphItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    status: Annotated[str, classified("internal")]
    retrievability_tier: Annotated[str | None, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    screening_action: Annotated[str | None, classified("internal")]


class GraphAccountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("confidential")]
    name: Annotated[str, classified("confidential")]
    balance: Annotated[Decimal, classified("confidential")]


class GraphAreaOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str | None, classified("internal")]
    name: Annotated[str, classified("confidential")]
    items: Annotated[list[GraphItemOut], classified("confidential")]
    accounts: Annotated[list[GraphAccountOut], classified("confidential")]


class CoverageGapsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    areas_without_requests: Annotated[list[str], classified("confidential")]
    areas_with_accounts_without_requests: Annotated[list[str], classified("confidential")]
    unmapped_accounts: Annotated[list[GraphAccountOut], classified("confidential")]
    items_without_evidence: Annotated[list[UUID], classified("internal")]


class GraphTeamMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[str, classified("internal")]


class GraphEngagementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    client_name: Annotated[str, classified("confidential")]
    client_entity_name: Annotated[str, classified("confidential")]
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    status: Annotated[str, classified("internal")]


class GraphMethodologyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]


class EngagementGraphOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement: Annotated[GraphEngagementOut, classified("confidential")]
    team: Annotated[list[GraphTeamMemberOut], classified("confidential")]
    methodology: Annotated[GraphMethodologyOut | None, classified("internal")]
    snapshot_id: Annotated[UUID | None, classified("internal")]
    areas: Annotated[list[GraphAreaOut], classified("confidential")]
    unmapped_accounts: Annotated[list[GraphAccountOut], classified("confidential")]
    gaps: Annotated[CoverageGapsOut, classified("confidential")]


def _graph_out(graph: EngagementGraph) -> EngagementGraphOut:
    view = graph.metadata.engagement
    m = graph.methodology
    return EngagementGraphOut(
        engagement=GraphEngagementOut(
            id=view.id,
            name=view.name,
            client_name=view.client_name,
            client_entity_name=view.client_entity_name,
            fiscal_period_start=view.fiscal_period_start,
            fiscal_period_end=view.fiscal_period_end,
            status=view.status,
        ),
        team=[
            GraphTeamMemberOut(user_id=t.user_id, display_name=t.display_name, role=t.role)
            for t in graph.metadata.team
        ],
        methodology=GraphMethodologyOut(
            template_id=m.template_id,
            template_name=m.template_name,
            version_id=m.version_id,
            version=m.version,
        )
        if m is not None
        else None,
        snapshot_id=graph.snapshot_id,
        areas=[GraphAreaOut.model_validate(asdict(a)) for a in graph.areas],
        unmapped_accounts=[
            GraphAccountOut.model_validate(asdict(a)) for a in graph.unmapped_accounts
        ],
        gaps=CoverageGapsOut.model_validate(asdict(graph.gaps)),
    )


@graph_router.get("", action="engagement.read", response_model=EngagementGraphOut)
async def engagement_graph_route(engagement_id: UUID, ctx: Ctx) -> EngagementGraphOut:
    return _graph_out(await engagement_graph(ctx, engagement_id))
