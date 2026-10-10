"""Public interface of the agents module; other modules import only this (ADR-008)."""

from abacus.modules.agents.activities import ACTIVITIES
from abacus.modules.agents.citations import SheetLayoutError
from abacus.modules.agents.citations import verify as verify_citations
from abacus.modules.agents.engagement_agent_workflow import HANDLE as ENGAGEMENT_AGENT_HANDLE
from abacus.modules.agents.engagement_agent_workflow import EngagementAgent
from abacus.modules.agents.fake_responses import SCREEN_PROMPT, screening_responder
from abacus.modules.agents.fake_responses import install as install_fake_responses
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.handoff import Citation, Handoff, ScreeningOutput, VerifiedCitation
from abacus.modules.agents.knowledge import KnowledgeHit, knowledge_context, search_knowledge
from abacus.modules.agents.routes import graph_router, knowledge_router, router
from abacus.modules.agents.screenings import (
    SUBSCRIPTIONS,
    WORKFLOWS,
    start_screening,
    workflow_id,
)
from abacus.modules.agents.service import (
    SCREENER,
    AgentRunBusy,
    AgentRunNotRunning,
    RunOutcome,
    ScreeningOutcome,
    ScreeningResultView,
    create_screening_run,
    fail_run,
    load_agent_context,
    proposal_of,
    proposals_for,
    run_outcome,
    screen,
    screening_results_for,
)
from abacus.modules.agents.spec import AGENTS, AgentSpec, spec
from abacus.modules.agents.workflow_types import (
    AgentEvent,
    AgentInput,
    HandleInput,
    HandleResult,
    ScreeningInput,
)
from abacus.modules.agents.workflows import ScreeningWorkflow
from abacus.modules.evidence.api import register_proposal_source

# Evidence owns review decisions; agents owns what was proposed (TASK-019 D1).
register_proposal_source(proposals_for, proposal_of)

__all__ = [
    "ACTIVITIES",
    "AGENTS",
    "ENGAGEMENT_AGENT_HANDLE",
    "SCREENER",
    "SCREEN_PROMPT",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AgentEvent",
    "AgentInput",
    "AgentRunBusy",
    "AgentRunNotRunning",
    "AgentSpec",
    "Citation",
    "EngagementAgent",
    "EngagementGraph",
    "HandleInput",
    "HandleResult",
    "Handoff",
    "KnowledgeHit",
    "RunOutcome",
    "ScreeningInput",
    "ScreeningOutcome",
    "ScreeningOutput",
    "ScreeningResultView",
    "ScreeningWorkflow",
    "SheetLayoutError",
    "VerifiedCitation",
    "create_screening_run",
    "engagement_graph",
    "fail_run",
    "graph_router",
    "install_fake_responses",
    "knowledge_context",
    "knowledge_router",
    "load_agent_context",
    "router",
    "run_outcome",
    "screen",
    "screening_responder",
    "screening_results_for",
    "search_knowledge",
    "spec",
    "start_screening",
    "verify_citations",
    "workflow_id",
]
