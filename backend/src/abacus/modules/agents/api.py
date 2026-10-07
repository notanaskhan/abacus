"""Public interface of the agents module; other modules import only this (ADR-008)."""

from abacus.modules.agents.activities import ACTIVITIES
from abacus.modules.agents.citations import SheetLayoutError
from abacus.modules.agents.citations import verify as verify_citations
from abacus.modules.agents.fake_responses import SCREEN_PROMPT, screening_responder
from abacus.modules.agents.fake_responses import install as install_fake_responses
from abacus.modules.agents.handoff import Citation, Handoff, ScreeningOutput, VerifiedCitation
from abacus.modules.agents.routes import router
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
    run_outcome,
    screen,
    screening_results_for,
)
from abacus.modules.agents.spec import AGENTS, AgentSpec, spec
from abacus.modules.agents.workflow_types import ScreeningInput
from abacus.modules.agents.workflows import ScreeningWorkflow

__all__ = [
    "ACTIVITIES",
    "AGENTS",
    "SCREENER",
    "SCREEN_PROMPT",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AgentRunBusy",
    "AgentRunNotRunning",
    "AgentSpec",
    "Citation",
    "Handoff",
    "RunOutcome",
    "ScreeningInput",
    "ScreeningOutcome",
    "ScreeningOutput",
    "ScreeningResultView",
    "ScreeningWorkflow",
    "SheetLayoutError",
    "VerifiedCitation",
    "create_screening_run",
    "fail_run",
    "install_fake_responses",
    "load_agent_context",
    "router",
    "run_outcome",
    "screen",
    "screening_responder",
    "screening_results_for",
    "spec",
    "start_screening",
    "verify_citations",
    "workflow_id",
]
