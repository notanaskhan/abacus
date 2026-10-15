"""Public interface of the agents module; other modules import only this (ADR-008)."""

from abacus.modules.agents.activities import ACTIVITIES
from abacus.modules.agents.citations import SheetLayoutError
from abacus.modules.agents.citations import verify as verify_citations
from abacus.modules.agents.engagement_agent import start_agents
from abacus.modules.agents.engagement_agent_workflow import HANDLE as ENGAGEMENT_AGENT_HANDLE
from abacus.modules.agents.engagement_agent_workflow import (
    NEXT_TICK as ENGAGEMENT_AGENT_NEXT_TICK,
)
from abacus.modules.agents.engagement_agent_workflow import EngagementAgent
from abacus.modules.agents.fake_responses import SCREEN_PROMPT, screening_responder
from abacus.modules.agents.fake_responses import install as install_fake_responses
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.guidance_draft import DRAFTER, DraftOutcome, create_draft_run, draft
from abacus.modules.agents.handoff import Citation, Handoff, ScreeningOutput, VerifiedCitation
from abacus.modules.agents.inbox_match import MATCHER, MatchOutcome, create_match_run, match
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
from abacus.modules.agents.upload_review import (
    REVIEWER,
    ReviewOutcome,
    create_review_run,
    review,
)
from abacus.modules.agents.workflow_types import (
    AgentEvent,
    AgentInput,
    HandleInput,
    HandleResult,
    MatchInput,
    MatchRunInput,
    NextTickInput,
    RunInput,
    ScreeningInput,
    SlotGrant,
)
from abacus.modules.agents.workflows import (
    InboxMatchWorkflow,
    ScreeningWorkflow,
    UploadReviewWorkflow,
)
from abacus.modules.evidence.api import register_proposal_source

# Evidence owns review decisions; agents owns what was proposed (TASK-019 D1).
register_proposal_source(proposals_for, proposal_of)

__all__ = [
    "ACTIVITIES",
    "AGENTS",
    "DRAFTER",
    "ENGAGEMENT_AGENT_HANDLE",
    "ENGAGEMENT_AGENT_NEXT_TICK",
    "MATCHER",
    "REVIEWER",
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
    "DraftOutcome",
    "EngagementAgent",
    "EngagementGraph",
    "HandleInput",
    "HandleResult",
    "Handoff",
    "InboxMatchWorkflow",
    "KnowledgeHit",
    "MatchInput",
    "MatchOutcome",
    "MatchRunInput",
    "NextTickInput",
    "ReviewOutcome",
    "RunInput",
    "RunOutcome",
    "ScreeningInput",
    "ScreeningOutcome",
    "ScreeningOutput",
    "ScreeningResultView",
    "ScreeningWorkflow",
    "SheetLayoutError",
    "SlotGrant",
    "UploadReviewWorkflow",
    "VerifiedCitation",
    "create_draft_run",
    "create_match_run",
    "create_review_run",
    "create_screening_run",
    "draft",
    "engagement_graph",
    "fail_run",
    "graph_router",
    "install_fake_responses",
    "knowledge_context",
    "knowledge_router",
    "load_agent_context",
    "match",
    "review",
    "router",
    "run_outcome",
    "screen",
    "screening_responder",
    "screening_results_for",
    "search_knowledge",
    "spec",
    "start_agents",
    "start_screening",
    "verify_citations",
    "workflow_id",
]
