"""The engagement run's `workpaper` step (P-10-T39; DEC-3404), registered by its owner.

`agents.engagement_run` plans one `run_step.workpaper` per EBP section with the bound paper's
code; this handler is the readiness check: the paper exists in the engagement's file. Preparing
a paper is its section's own registered handler's (A-04, A-05). Registered at the workpapers api's
import, so agents never reads the `workpapers` table (ADR-008, OWN-001, BOUND-002).
"""

from __future__ import annotations

from abacus.modules.agents.api import RunStepFacts, RunStepResult, register_run_step
from abacus.modules.identity.api import AgentContext
from abacus.modules.workpapers.audit_labels import workpaper_code_exists


async def workpaper_ready(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    code = facts.arguments.get("workpaper_code")
    if not isinstance(code, str):
        return RunStepResult("succeeded")  # a section with no bound paper: nothing to check
    if not await workpaper_code_exists(agent.tenant, facts.engagement_id, code):
        return RunStepResult("failed", "workpaper_missing")
    return RunStepResult("succeeded", records_read=1)


def register() -> None:
    register_run_step("workpaper", workpaper_ready)
