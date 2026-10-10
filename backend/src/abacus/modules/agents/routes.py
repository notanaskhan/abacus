"""Agent routes (SPEC-000 §8; TASK-012 Q1): screening results for the evidence board. Read-only:
agents propose, and nothing here lets anyone act on a proposal (ADR-005)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.agents.engagement_agent import (
    AgentView,
    activity_feed,
    agent_view,
    set_paused,
)
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.knowledge import (
    DocumentView,
    MediaType,
    NewDocument,
    SourceKind,
    add_document,
    document,
    documents,
    search_knowledge,
    withdraw_document,
)
from abacus.modules.agents.screenings import request_screening
from abacus.modules.agents.service import ScreeningResultView, screening_results_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

# One router for the engagement's agent surfaces (screening results; SPEC-027's agent and feed).
router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["agents"])
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


@router.get("/screening-results", action="evidence.read", response_model=list[ScreeningResultOut])
async def list_screening_results_route(engagement_id: UUID, ctx: Ctx) -> list[ScreeningResultOut]:
    return [_out(r) for r in await screening_results_for(ctx, engagement_id)]


class ScreenRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]


class ScreenRequestedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]


@router.post(
    "/screening-results/request",
    action="screening.request",
    response_model=ScreenRequestedOut,
    status_code=202,
)
async def request_screening_route(
    engagement_id: UUID, body: ScreenRequestIn, ctx: Ctx
) -> ScreenRequestedOut:
    """SPEC-024 (TASK-042 D1): "Screen now"; the result appears with the others when ready."""
    await request_screening(ctx, engagement_id, body.evidence_version_id)
    return ScreenRequestedOut(evidence_version_id=body.evidence_version_id)


# --- The engagement agent (SPEC-027; TASK-050) ---------------------------------------------------


class AgentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: Annotated[bool, classified("internal")]
    paused_at: Annotated[datetime | None, classified("internal")]
    paused_by: Annotated[str | None, classified("confidential")]
    reason: Annotated[str | None, classified("confidential")]
    firm_paused_at: Annotated[datetime | None, classified("internal")]


class PauseIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[str | None, Field(max_length=300), classified("confidential")] = None


class ActivityOut(BaseModel):
    """One automatic action: references only, never client content (AC-7)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    policy: Annotated[str, classified("internal")]
    policy_version: Annotated[int, classified("internal")]
    action: Annotated[str, classified("internal")]
    outcome: Annotated[Literal["done", "skipped", "failed"], classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    record_type: Annotated[str | None, classified("internal")]
    record_id: Annotated[UUID | None, classified("internal")]
    item_count: Annotated[int | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


def _agent_out(view: AgentView) -> AgentOut:
    return AgentOut.model_validate(asdict(view))


@router.get("/agent", action="activity.read", response_model=AgentOut)
async def agent_route(engagement_id: UUID, ctx: Ctx) -> AgentOut:
    """SPEC-027: whether the agent is on, and the engagement's and the firm's pause."""
    return _agent_out(await agent_view(ctx, engagement_id))


@router.post("/agent/pause", action="agent.pause", response_model=AgentOut)
async def pause_agent_route(engagement_id: UUID, body: PauseIn, ctx: Ctx) -> AgentOut:
    """SPEC-027 AC-6: nothing automatic happens on this engagement until resumed."""
    return _agent_out(await set_paused(ctx, engagement_id, paused=True, reason=body.reason))


@router.post("/agent/resume", action="agent.pause", response_model=AgentOut)
async def resume_agent_route(engagement_id: UUID, ctx: Ctx) -> AgentOut:
    """SPEC-027 AC-6: the agent looks once: what arrived while paused is screened."""
    return _agent_out(await set_paused(ctx, engagement_id, paused=False))


@router.get("/activity", action="activity.read", response_model=list[ActivityOut])
async def activity_route(
    engagement_id: UUID,
    ctx: Ctx,
    before: datetime | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> list[ActivityOut]:
    """SPEC-027 AC-7: the activity feed, newest first."""
    rows = await activity_feed(ctx, engagement_id, before, limit)
    return [ActivityOut.model_validate(r, from_attributes=True) for r in rows]


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


# --- Knowledge (SPEC-009 §8) -------------------------------------------------------------------

knowledge_router = AbacusRouter(prefix="/v1/knowledge", tags=["knowledge"])


class KnowledgeDocumentIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), classified("internal")]
    source_kind: Annotated[SourceKind, classified("internal")]
    media_type: Annotated[MediaType, classified("internal")]
    text: Annotated[str, Field(min_length=1), classified("internal")]


class KnowledgeDocumentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    media_type: Annotated[str, classified("internal")]
    status: Annotated[
        Literal["pending", "ready", "failed", "withdrawn", "stale"], classified("internal")
    ]
    failure_code: Annotated[str | None, classified("internal")]
    chunk_count: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class KnowledgeSearchIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: Annotated[str, Field(min_length=1, max_length=1000), classified("internal")]
    k: Annotated[int, Field(ge=1, le=20), classified("internal")] = 8


class KnowledgeHitOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    heading_path: Annotated[str, classified("internal")]
    position: Annotated[int, classified("internal")]
    text: Annotated[str, classified("internal")]
    score: Annotated[float, classified("internal")]


def _document_out(view: DocumentView) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut.model_validate(asdict(view))


@knowledge_router.post(
    "/documents",
    action="knowledge.manage",
    response_model=KnowledgeDocumentOut,
    status_code=201,
    errors=(409,),
)
async def add_document_route(body: KnowledgeDocumentIn, ctx: Ctx) -> KnowledgeDocumentOut:
    document_id = await add_document(
        ctx, NewDocument(body.title, body.source_kind, body.media_type, body.text)
    )
    return _document_out(await document(ctx, document_id))


@knowledge_router.get(
    "/documents", action="knowledge.read", response_model=list[KnowledgeDocumentOut]
)
async def list_documents_route(ctx: Ctx) -> list[KnowledgeDocumentOut]:
    return [_document_out(v) for v in await documents(ctx)]


@knowledge_router.get(
    "/documents/{document_id}", action="knowledge.read", response_model=KnowledgeDocumentOut
)
async def get_document_route(document_id: UUID, ctx: Ctx) -> KnowledgeDocumentOut:
    return _document_out(await document(ctx, document_id))


@knowledge_router.post(
    "/documents/{document_id}/withdraw",
    action="knowledge.manage",
    response_model=KnowledgeDocumentOut,
    errors=(409,),
)
async def withdraw_document_route(document_id: UUID, ctx: Ctx) -> KnowledgeDocumentOut:
    await withdraw_document(ctx, document_id)
    return _document_out(await document(ctx, document_id))


@knowledge_router.post("/search", action="knowledge.read", response_model=list[KnowledgeHitOut])
async def search_route(body: KnowledgeSearchIn, ctx: Ctx) -> list[KnowledgeHitOut]:
    hits = await search_knowledge(ctx, body.query, body.k)
    return [KnowledgeHitOut.model_validate(asdict(h)) for h in hits]
