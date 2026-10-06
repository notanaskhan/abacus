"""Public interface of the agents module; other modules import only this (ADR-008)."""

from abacus.modules.agents.citations import SheetLayoutError
from abacus.modules.agents.citations import verify as verify_citations
from abacus.modules.agents.fake_responses import install as install_fake_responses
from abacus.modules.agents.handoff import Citation, Handoff, ScreeningOutput, VerifiedCitation
from abacus.modules.agents.service import (
    SCREENER,
    AgentRunNotRunning,
    ScreeningOutcome,
    create_screening_run,
    fail_run,
    load_agent_context,
    screen,
)
from abacus.modules.agents.spec import AGENTS, AgentSpec, spec

__all__ = [
    "AGENTS",
    "SCREENER",
    "AgentRunNotRunning",
    "AgentSpec",
    "Citation",
    "Handoff",
    "ScreeningOutcome",
    "ScreeningOutput",
    "SheetLayoutError",
    "VerifiedCitation",
    "create_screening_run",
    "fail_run",
    "install_fake_responses",
    "load_agent_context",
    "screen",
    "spec",
    "verify_citations",
]
