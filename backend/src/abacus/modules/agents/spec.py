"""Agent specifications (ADR-047). PROTECTED. TASK-011 design §3.

Every agent is declared in `specs/<id>.yaml` (compiled into `specs/_specs.py`) and validated here
at import: an agent without a valid spec can't run. Code must match its spec: the runtime reads
the prompt, tier, limits, task scope and untrusted inputs from here, not from constants.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from abacus.ai_gateway import Tier, prompt
from abacus.kernel.classification import classified
from abacus.modules.agents.specs._specs import SPECS
from abacus.modules.identity.api import agent_may_hold


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_output_tokens: Annotated[int, Field(gt=0, le=8_000), classified("internal")]
    max_cost_usd: Annotated[Decimal, Field(gt=0), classified("internal")]
    max_steps: Annotated[int, Field(ge=1), classified("internal")]
    max_seconds: Annotated[int, Field(ge=1), classified("internal")]


class ConfidenceRouting(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    below: Annotated[Decimal, Field(ge=0, le=1), classified("internal")]
    route: Annotated[Literal["ready_for_review", "needs_revision"], classified("internal")]


class AgentSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[
        str, Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"), classified("internal")
    ]
    version: Annotated[int, Field(ge=1), classified("internal")]
    purpose: Annotated[str, Field(min_length=1), classified("internal")]
    shape: Annotated[Literal["single_call"], classified("internal")]
    prompt: Annotated[str, classified("internal")]
    tier: Annotated[Tier, classified("internal")]
    escalation_tier: Annotated[Tier, classified("internal")]
    input_schema: Annotated[str, classified("internal")]
    output_schema: Annotated[str, classified("internal")]
    task_scope: Annotated[frozenset[str], classified("internal")]
    tools: Annotated[tuple[str, ...], classified("internal")]
    limits: Annotated[Limits, classified("internal")]
    # ADR-005: agents propose; humans decide.
    autonomy: Annotated[Literal["propose"], classified("internal")]
    confidence_routing: Annotated[ConfidenceRouting, classified("internal")]
    untrusted_inputs: Annotated[frozenset[str], classified("internal")]
    evaluation_suite: Annotated[
        str, Field(pattern=r"^evals/[a-z][a-z0-9_/]*$"), classified("internal")
    ]


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
