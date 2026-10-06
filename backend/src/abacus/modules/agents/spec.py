"""Agent specifications (ADR-047). PROTECTED. TASK-011 design §3.

Every agent is declared in `specs/<id>.yaml` (compiled into `specs/_specs.py`) and validated here
at import: an agent without a valid spec can't run. Code must match its spec: the runtime reads
the prompt, tier, limits, task scope and untrusted inputs from here, not from constants.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from abacus.ai_gateway import Tier, prompt
from abacus.modules.agents.specs._specs import SPECS
from abacus.modules.identity.api import agent_may_hold


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_output_tokens: int = Field(gt=0, le=8_000)
    max_cost_usd: Decimal = Field(gt=0)
    max_steps: int = Field(ge=1)
    max_seconds: int = Field(ge=1)


class ConfidenceRouting(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    below: Decimal = Field(ge=0, le=1)
    route: Literal["ready_for_review", "needs_revision"]


class AgentSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    version: int = Field(ge=1)
    purpose: str = Field(min_length=1)
    shape: Literal["single_call"]
    prompt: str
    tier: Tier
    escalation_tier: Tier
    input_schema: str
    output_schema: str
    task_scope: frozenset[str]
    tools: tuple[str, ...]
    limits: Limits
    autonomy: Literal["propose"]  # ADR-005: agents propose; humans decide
    confidence_routing: ConfidenceRouting
    untrusted_inputs: frozenset[str]
    evaluation_suite: str = Field(pattern=r"^evals/[a-z][a-z0-9_/]*$")


def _load() -> dict[str, AgentSpec]:
    loaded = {agent_id: AgentSpec.model_validate(raw) for agent_id, raw in SPECS.items()}
    for spec in loaded.values():
        prompt(spec.prompt)  # a spec must name a registered prompt version
        # ADR-005, ADR-025: a task scope holds only actions the matrix lets agents be given.
        refused = sorted(a for a in spec.task_scope if not agent_may_hold(a))
        if refused:
            raise ValueError(f"agent {spec.id}: task scope may not include {refused}")
    return loaded


AGENTS: dict[str, AgentSpec] = _load()


def spec(agent_id: str) -> AgentSpec:
    found = AGENTS.get(agent_id)
    if found is None:
        raise LookupError(f"no agent spec {agent_id!r}: agents run only from a spec")
    return found
