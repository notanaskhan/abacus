"""`runtime.conformance` v1, the reference loop capability (P-10-T40; SPEC-647 §3.3, §6; P-10 §8.2;
ADR-234, ADR-049, ADR-052, ADR-005; DEC-3403). PROTECTED (agents).

It proves the runtime end to end: `converse()` turns through the gateway, the loop harness's
limits and provenance rules, C17's tool registry and runtime (scope, rights, §7216, grants) and the
trajectory graders, on the fake route in tests and CI and on the direct and Bedrock routes in the
evaluation account (P-10-T46). It is never a product:

- **Synthetic only, never installable, no firm endpoint.** `TEST_ONLY` names it; `run_conformance`
  refuses a firm that is not synthetic (404, so nothing about it is disclosed), and
  `run_start.open_capability_run` refuses any `TEST_ONLY` capability for a real firm. No route
  module names it (a unit test reads every route module).
- **The harness's first concrete ports** (`ConversePorts`): each turn is one `converse()` call
  with the spec's prompt, tier, budget, routes and output schema, offering the spec's registered
  tools (each described by its own registry prompt); each tool call goes through `call_tool` with
  the run's `AgentContext`, its result handed back as `for_model` renders it (untrusted fields in
  `<untrusted>` blocks). The conversation is identifiers, codes and wrapped tool results only.

The output schema (`ConformanceOutput`) is the harness's contract: `question` (ask when ambiguous),
`plan` (a declared write needs approval first), or `blocks` (the cited answer, settled against the
run's verified citations before it is emitted).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.ai_gateway import Attribution
from abacus.ai_gateway import providers as p
from abacus.ai_gateway.converse import ConverseCall, ConverseTool, converse
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.modules.agents.harness import (
    HarnessOutcome,
    Limits,
    ToolRequest,
    ToolResult,
    TurnResult,
    run_step,
)
from abacus.modules.agents.service import load_run_v2_context
from abacus.modules.agents.spec_v2 import AgentSpecV2, spec_v2
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.agents.tools.runtime import ToolCallIn, call_tool, for_model
from abacus.modules.identity.api import AgentContext, is_synthetic_firm

CAPABILITY: Final = "runtime.conformance"
Int = classified("internal")
Conf = classified("confidential")


class ConformanceInput(BaseModel):
    """The person's request (the first user turn): text, never instructions to the runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: Annotated[str, Field(min_length=1, max_length=2_000), classified("restricted")]


class ConformanceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: Annotated[str, Field(min_length=1, max_length=300), Conf]
    options: Annotated[list[str], Field(min_length=2, max_length=4), Conf]


class ConformancePlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: Annotated[str, Field(min_length=1, max_length=200), Conf]
    tool: Annotated[str | None, Field(max_length=80), Int] = None
    write: Annotated[bool, Int] = False
    # S37 end pass (DEC-4317): the tool's arguments, validated against its input model before a
    # child run is written, shown in the plan the person approves, checked again by C17 per call.
    arguments: Annotated[dict[str, object] | None, Conf] = None  # a JSON object


class ConformancePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: Annotated[list[ConformancePlanStep], Field(min_length=1, max_length=14), Conf]


class ConformanceOutput(BaseModel):
    """The structured final turn: exactly one of `question`, `plan` or `blocks` (C6 v2 blocks)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: Annotated[ConformanceQuestion | None, Conf] = None
    plan: Annotated[ConformancePlan | None, Conf] = None
    blocks: Annotated[dict[str, object] | None, Conf] = None


def limits_of(spec: AgentSpecV2) -> Limits:
    return Limits(
        max_steps=spec.limits.max_steps,
        max_seconds=spec.limits.max_seconds,
        max_cost_usd=spec.limits.max_cost_usd,
        max_tool_calls=spec.limits.max_tool_calls,
        max_repeat_identical_calls=spec.limits.max_repeat_identical_calls,
    )


def converse_tools(spec: AgentSpecV2) -> tuple[ConverseTool, ...]:
    """The spec's registered tools as `converse()` offers them (ADR-049: each description is the
    tool's registry prompt)."""
    found = registered_tools()
    tools: list[ConverseTool] = []
    for name in spec.tools.names():
        registered = found[name]
        tools.append(
            ConverseTool(
                spec=p.ToolSpec(
                    name,
                    registered.description,
                    registered.input_model.model_json_schema(),
                ),
                input_model=registered.input_model,
            )
        )
    return tuple(tools)


@dataclass
class ConversePorts:
    """`HarnessPorts` over `converse()` and C17 for one run step."""

    agent: AgentContext
    spec: AgentSpecV2
    step_seq: int
    request: str
    tools: tuple[ConverseTool, ...] = ()
    messages: list[p.ConverseMessage] = field(default_factory=list[p.ConverseMessage])
    _pending: list[p.ToolResultBlock] = field(default_factory=list[p.ToolResultBlock])
    _calls: int = 0
    _spent: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        self.tools = converse_tools(self.spec)
        self.messages.append(p.ConverseMessage("user", (p.TextBlock(self.request),)))

    def _flush(self) -> None:
        if self._pending:
            self.messages.append(p.ConverseMessage("user", tuple(self._pending)))
            self._pending = []

    async def turn(self, history: tuple[Mapping[str, object], ...]) -> TurnResult:
        del history  # the conversation is held here, in the provider's blocks
        self._flush()
        result = await converse(
            ConverseCall(
                purpose=f"{self.spec.id} step {self.step_seq}",
                prompt=self.spec.prompt,
                tier=self.spec.tier,
                budget_usd=self.spec.limits.max_cost_usd - self._spent,
                attribution=Attribution(
                    self.agent.tenant,
                    self.agent.engagement_id,
                    self.spec.id,
                    self.agent.agent_run_id,
                ),
                work_class=self.spec.work_class,
                essential=self.spec.essential,
                routes=self.spec.routes,
                messages=tuple(self.messages),
                tools=self.tools,
                output_schema=ConformanceOutput,
                max_output_tokens=self.spec.limits.max_output_tokens,
                cheaper_tiers=self.spec.cheaper_tiers,
            )
        )
        self._spent += result.cost_usd
        if result.status == "tool_use":
            requests = tuple(
                ToolRequest(c.tool_use_id, c.name, c.arguments.model_dump(mode="json"))
                for c in result.tool_calls
            )
            self.messages.append(
                p.ConverseMessage(
                    "assistant",
                    tuple(p.ToolUseBlock(r.tool_use_id, r.name, r.arguments) for r in requests),
                )
            )
            return TurnResult("tool_calls", result.cost_usd, tool_calls=requests)
        if result.status in ("ok", "repaired") and result.output is not None:
            output = result.output.model_dump(mode="json", exclude_none=True)
            return TurnResult("ok", result.cost_usd, output=output)
        return TurnResult("escalated", result.cost_usd, failure=result.failure or "escalated")

    async def tool(self, request: ToolRequest) -> ToolResult:
        self._calls += 1
        outcome = await call_tool(
            self.agent,
            ToolCallIn(
                run_id=self.agent.agent_run_id,
                step_seq=self.step_seq,
                attempt=self._calls,
                name=request.name,
                arguments=dict(request.arguments),
            ),
        )
        self._pending.append(
            p.ToolResultBlock(request.tool_use_id, for_model(outcome), is_error=not outcome.ok)
        )
        return ToolResult(
            name=request.name,
            ok=outcome.ok,
            code=outcome.code,
            records_read=outcome.records_read,
            payload=outcome.result if outcome.ok else None,
        )


async def run_conformance(
    tenant_id: UUID,
    run_id: UUID,
    request: str,
    *,
    step_seq: int = 1,
    citations: Sequence[UUID] = (),
) -> HarnessOutcome:
    """One `runtime.conformance` step for a run on a synthetic firm (module docstring)."""
    agent = await load_run_v2_context(tenant_id, run_id)
    if agent.agent_id != CAPABILITY or not await is_synthetic_firm(agent.tenant):
        raise NotFound("agent_run")
    spec = spec_v2(CAPABILITY)
    ports = ConversePorts(agent, spec, step_seq, ConformanceInput(request=request).request)
    return await run_step(
        ports,
        limits_of(spec),
        facts={},
        citations=set(citations),
        first_turn={"role": "user", "kind": "request"},
    )
