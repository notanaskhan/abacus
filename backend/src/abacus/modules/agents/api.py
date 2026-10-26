"""Public interface of the agents module; other modules import only this (ADR-008)."""

from abacus.ai_gateway import (
    BoundaryFactsChanged,
    on_boundary_facts_changed,
    register_client_data_facts,
)
from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.agents.activities import ACTIVITIES
from abacus.modules.agents.ai_policy_errors import AiPolicyLoosened, ApproverMustDiffer
from abacus.modules.agents.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.agents.citations import SheetLayoutError
from abacus.modules.agents.citations import verify as verify_citations
from abacus.modules.agents.contract import proposals_router, suggestions_router
from abacus.modules.agents.engagement_agent import start_agents
from abacus.modules.agents.engagement_agent_workflow import HANDLE as ENGAGEMENT_AGENT_HANDLE
from abacus.modules.agents.engagement_agent_workflow import (
    NEXT_TICK as ENGAGEMENT_AGENT_NEXT_TICK,
)
from abacus.modules.agents.engagement_agent_workflow import EngagementAgent
from abacus.modules.agents.entry_assess import ASSESSOR, ask, check
from abacus.modules.agents.events import FollowUpSent
from abacus.modules.agents.export_screening import screening_section
from abacus.modules.agents.fake_responses import SCREEN_PROMPT, screening_responder
from abacus.modules.agents.fake_responses import install as install_fake_responses
from abacus.modules.agents.follow_up_drafts import on_follow_up_sent
from abacus.modules.agents.follow_up_routes import follow_ups_router
from abacus.modules.agents.gates import register_gate_sources, register_suggestion_lookup
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.guidance_draft import DRAFTER, DraftOutcome, create_draft_run, draft
from abacus.modules.agents.handoff import Citation, Handoff, ScreeningOutput, VerifiedCitation
from abacus.modules.agents.inbox_match import MATCHER, MatchOutcome, create_match_run, match
from abacus.modules.agents.knowledge import KnowledgeHit, knowledge_context, search_knowledge
from abacus.modules.agents.proposal_slots import (
    UnregisteredTarget,
    apply_proposal,
    check_suggestion_target,
    register_proposal_adapter,
    register_suggestion_target,
)
from abacus.modules.agents.review_start import (
    CitationStates,
    ReviewUnavailable,
    request_review,
    review_citation_states,
)
from abacus.modules.agents.routes import (
    graph_router,
    knowledge_router,
    router,
    template_drafts_router,
)
from abacus.modules.agents.runs_routes import engagement_runs_router, runs_router
from abacus.modules.agents.screening_contract import screening_items_router, screenings_router
from abacus.modules.agents.screenings import (
    SUBSCRIPTIONS as SCREENING_SUBSCRIPTIONS,
)
from abacus.modules.agents.screenings import (
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
from abacus.modules.agents.spec import AGENTS, AgentSpec, cleared_for_client_data, spec
from abacus.modules.agents.stage_routes import platform_stages_router
from abacus.modules.agents.stages import assistants, stage_for
from abacus.modules.agents.upload_review import (
    REVIEWER,
    ReviewOutcome,
    create_review_run,
    review,
)
from abacus.modules.agents.upload_review import model_available as upload_review_available
from abacus.modules.agents.workflow_types import (
    AgentEvent,
    AgentInput,
    EntryAssessInput,
    EntryAssessRunInput,
    GuidanceDraftInput,
    GuidanceDraftRunInput,
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
    EntryAssessWorkflow,
    GuidanceDraftWorkflow,
    InboxMatchWorkflow,
    ScreeningWorkflow,
    UploadReviewWorkflow,
)
from abacus.modules.evidence.api import register_export_section, register_proposal_source
from abacus.modules.identity.api import AbacusRouter, register_ai_assistants

# Evidence owns review decisions; agents owns what was proposed (TASK-019 D1).
register_proposal_source(proposals_for, proposal_of)
# A-01-T19 (SPEC-344 §6): screening results are the export's `provenance/screening.csv`.
register_export_section("screening", screening_section)
# SPEC-036 (TASK-075): which agents may see a real firm's data (stages follow in TASK-076).
register_client_data_facts(cleared=cleared_for_client_data, stage=stage_for)
# SPEC-036 (TASK-076): identity's disclosure lists the cleared assistants and their stage.
register_ai_assistants(assistants)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    graph_router,
    knowledge_router,
    template_drafts_router,
    engagement_runs_router,
    runs_router,
    # C3 stubs behind `review.grammar_api` (P-04-T08; ADR-161).
    proposals_router,
    suggestions_router,
    follow_ups_router,  # P-06-T14: follow-ups v2 behind `binders.engine`
    # C5 v1.2 SHL-20 family stub behind `screening.card` (P-06-T15).
    screening_items_router,
    screenings_router,
    platform_stages_router,  # Q-02-T07: platform staff set an agent's stage for a firm
)
# P-06-T14: a sent follow-up's email leaves when the relay delivers its grant-held event.
# Q-02-T08: a firm's changed boundary facts are forgotten in the worker too.
SUBSCRIPTIONS = {
    **SCREENING_SUBSCRIPTIONS,
    FollowUpSent.event_type: on_follow_up_sent,
    BoundaryFactsChanged.event_type: on_boundary_facts_changed,
}

# P-04-T16 (C13): the agent's proposals are `proposal` gates until a person decides.
register_gate_sources()
# P-04-T23: review checks a decision card's recommended suggestion against its engagement.
register_suggestion_lookup()

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "AGENTS",
    "ASSESSOR",
    "DRAFTER",
    "ENGAGEMENT_AGENT_HANDLE",
    "ENGAGEMENT_AGENT_NEXT_TICK",
    "MATCHER",
    "REVIEWER",
    "ROUTERS",
    "SCREENER",
    "SCREEN_PROMPT",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AgentEvent",
    "AgentInput",
    "AgentRunBusy",
    "AgentRunNotRunning",
    "AgentSpec",
    "AiPolicyLoosened",
    "ApproverMustDiffer",
    "Citation",
    "CitationStates",
    "DraftOutcome",
    "EngagementAgent",
    "EngagementGraph",
    "EntryAssessInput",
    "EntryAssessRunInput",
    "EntryAssessWorkflow",
    "GuidanceDraftInput",
    "GuidanceDraftRunInput",
    "GuidanceDraftWorkflow",
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
    "ReviewUnavailable",
    "RunInput",
    "RunOutcome",
    "ScreeningInput",
    "ScreeningOutcome",
    "ScreeningOutput",
    "ScreeningResultView",
    "ScreeningWorkflow",
    "SheetLayoutError",
    "SlotGrant",
    "UnregisteredTarget",
    "UploadReviewWorkflow",
    "VerifiedCitation",
    "apply_proposal",
    "ask",
    "check",
    "check_suggestion_target",
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
    "register_proposal_adapter",
    "register_suggestion_target",
    "request_review",
    "review",
    "review_citation_states",
    "router",
    "run_outcome",
    "screen",
    "screening_responder",
    "screening_results_for",
    "search_knowledge",
    "spec",
    "start_agents",
    "start_screening",
    "template_drafts_router",
    "upload_review_available",
    "verify_citations",
    "workflow_id",
]
