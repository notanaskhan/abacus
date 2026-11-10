"""Capability specs v2 (P-10-T20; ADR-047, ADR-233; SPEC-647 AC-R8; chapter 05 §5.3.3). PROTECTED.

v1 (`spec.py`, `specs/*.yaml`) stays exactly as it is: the four live `single_call` specialists and
the section drafter keep loading through `AgentSpec`. v2 adds the shapes a runtime capability
needs: `single_call`, `workflow`, `loop` and `conversation`; tools listed by kind (`read`,
`compute`, `propose`, `approved_write`); loop limits; a plan policy; data classes; untrusted
inputs.

Each `specs/v2/<id>.yaml` is compiled into `specs/_specs_v2.py` by
`python -m abacus_tools.codegen.agent_specs_v2` and validated twice:

- **here, at import** (`_load`): the rules that need only the spec itself, so a bad spec never
  loads: a `single_call` takes one step and lists no tools; a `loop` declares `max_tool_calls` and
  `max_repeat_identical_calls`; any `propose` or `approved_write` tool forces
  `plan: required_when_writes` (or `always`); `tri` loads only while C19's consent checks exist.
- **by the codegen** (`registry_problems`), which imports every module's `agent_tools.py` and reads
  the matrix: every tool is registered and of the kind the spec lists it under; its action is in
  the spec's `task_scope`; an `approved_write` tool's action is `agent: deny`; a read, compute or
  propose tool's action is one the agent may hold.

Firm agent definitions only narrow a capability (ADR-047); nothing here widens one. ADR-005 holds:
`autonomy` stays `propose`, and writes happen only under a person's approval grant.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from abacus.ai_gateway import Tier, prompt
from abacus.kernel.classification import classified
from abacus.kernel.dispatch import WorkClass
from abacus.modules.agents.specs._specs_v2 import SPECS_V2
from abacus.modules.identity.api import agent_denied, agent_may_hold, consent_registered

Shape = Literal["single_call", "workflow", "loop", "conversation"]
PlanPolicy = Literal["never", "required_when_writes", "always"]
DataClassV2 = Literal["internal", "confidential", "restricted", "tri"]
ToolKindV2 = Literal["read", "compute", "propose", "approved_write"]
TRI_CONSENT_PURPOSES: Final = ("use", "ai_disclosure")
WRITE_KINDS: Final = frozenset({"propose", "approved_write"})


class LimitsV2(BaseModel):
    """v1's limits plus the loop's. A `loop` must declare both call limits (AC-R8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_output_tokens: Annotated[int, Field(gt=0, le=8_000), classified("internal")]
    max_cost_usd: Annotated[Decimal, Field(gt=0), classified("internal")]
    max_steps: Annotated[int, Field(ge=1), classified("internal")]
    max_seconds: Annotated[int, Field(ge=1), classified("internal")]
    max_tool_calls: Annotated[int | None, Field(ge=1), classified("internal")] = None
    max_repeat_identical_calls: Annotated[int | None, Field(ge=1), classified("internal")] = None
    max_parallel_steps: Annotated[int | None, Field(ge=1), classified("internal")] = None


class ToolsByKind(BaseModel):
    """The spec's allow-list, by kind. A firm definition may narrow it, never widen it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    read: Annotated[tuple[str, ...], classified("internal")] = ()
    compute: Annotated[tuple[str, ...], classified("internal")] = ()
    propose: Annotated[tuple[str, ...], classified("internal")] = ()
    approved_write: Annotated[tuple[str, ...], classified("internal")] = ()

    def by_kind(self) -> dict[ToolKindV2, tuple[str, ...]]:
        return {
            "read": self.read,
            "compute": self.compute,
            "propose": self.propose,
            "approved_write": self.approved_write,
        }

    def names(self) -> list[str]:
        return [n for names in self.by_kind().values() for n in names]

    def writes(self) -> bool:
        return bool(self.propose or self.approved_write)


class AgentSpecV2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[
        str, Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"), classified("internal")
    ]
    version: Annotated[int, Field(ge=1), classified("internal")]
    purpose: Annotated[str, Field(min_length=1), classified("internal")]
    shape: Annotated[Shape, classified("internal")]
    prompt: Annotated[str, classified("internal")]
    # Each tool's description is its own registry prompt `tool.<name>@vN` (C17).
    tool_prompts: Annotated[bool, classified("internal")] = True
    tier: Annotated[Tier, classified("internal")]
    escalation_tier: Annotated[Tier, classified("internal")]
    input_schema: Annotated[str, Field(min_length=1), classified("internal")]
    output_schema: Annotated[str, Field(min_length=1), classified("internal")]
    tools: Annotated[ToolsByKind, classified("internal")] = ToolsByKind()
    task_scope: Annotated[frozenset[str], classified("internal")]
    limits: Annotated[LimitsV2, classified("internal")]
    plan: Annotated[PlanPolicy, classified("internal")] = "never"
    # ADR-005: agents propose; humans decide. Writes run only under a person's approval grant.
    autonomy: Annotated[Literal["propose"], classified("internal")] = "propose"
    data_classes: Annotated[frozenset[DataClassV2], classified("internal")] = frozenset(
        {"confidential"}
    )
    untrusted_inputs: Annotated[frozenset[str], classified("internal")]
    evaluation_suite: Annotated[
        str, Field(pattern=r"^evals/[a-z][a-z0-9_/]*$"), classified("internal")
    ]
    work_class: Annotated[WorkClass, classified("internal")]
    essential: Annotated[bool, classified("internal")] = False
    cheaper_tiers: Annotated[tuple[Tier, ...], classified("internal")] = ()
    routes: Annotated[
        tuple[Literal["direct", "bedrock"], ...], Field(min_length=1), classified("internal")
    ]
    # Cleared only with a committed Bedrock evaluation and Bedrock tool parity (SPEC-036, T13).
    client_data: Annotated[Literal["none", "cleared"], classified("internal")] = "none"


_ORDER: Final = {"small": 0, "medium": 1, "large": 2}


def spec_problems(
    spec: AgentSpecV2,
    *,
    consents: Callable[[str], bool] = consent_registered,
    holdable: Callable[[str], bool] = agent_may_hold,
) -> list[str]:
    """The rules a spec answers on its own (AC-R8). Empty means it loads."""
    found: list[str] = []
    names = spec.tools.names()
    if len(set(names)) != len(names):
        found.append(f"{spec.id}: a tool is listed once, under one kind")
    if len(set(spec.routes)) != len(spec.routes):
        found.append(f"{spec.id}: routes are listed once each")
    if spec.shape == "single_call":
        if spec.limits.max_steps != 1:
            found.append(f"{spec.id}: a single_call takes exactly one step")
        if names:
            found.append(f"{spec.id}: a single_call uses no tools")
    if spec.shape == "loop" and (
        spec.limits.max_tool_calls is None or spec.limits.max_repeat_identical_calls is None
    ):
        found.append(f"{spec.id}: a loop needs max_tool_calls and max_repeat_identical_calls")
    if spec.tools.writes() and spec.plan == "never":
        found.append(
            f"{spec.id}: a propose or approved_write tool needs plan: required_when_writes"
        )
    if "tri" in spec.data_classes and not all(consents(p) for p in TRI_CONSENT_PURPOSES):
        found.append(f"{spec.id}: data_classes tri needs the use and ai_disclosure consent checks")
    if any(_ORDER[t] >= _ORDER[spec.tier] for t in spec.cheaper_tiers):
        found.append(f"{spec.id}: cheaper_tiers must be cheaper than {spec.tier}")
    if _ORDER[spec.escalation_tier] < _ORDER[spec.tier]:
        found.append(f"{spec.id}: escalation_tier may not be below tier")
    refused = sorted(a for a in spec.task_scope if not holdable(a))
    if refused:
        found.append(f"{spec.id}: task scope may not include {refused}")
    return found


@dataclass(frozen=True)
class ToolFacts:
    """What the codegen knows of a registered tool (from C17's registry)."""

    kind: str
    action: str


def registry_problems(
    spec: AgentSpecV2,
    tools: Mapping[str, ToolFacts],
    *,
    denied: Callable[[str], bool],
    holdable: Callable[[str], bool],
) -> list[str]:
    """The rules that need C17's registry and the matrix (the codegen's; AC-R1, AC-R8)."""
    found: list[str] = []
    for kind, names in spec.tools.by_kind().items():
        for name in names:
            facts = tools.get(name)
            if facts is None:
                found.append(f"{spec.id}: tool {name} is not registered")
                continue
            if facts.kind != kind:
                found.append(f"{spec.id}: tool {name} is a {facts.kind} tool, listed as {kind}")
            if facts.action not in spec.task_scope:
                found.append(
                    f"{spec.id}: tool {name}'s action {facts.action} is outside task_scope"
                )
            if kind == "approved_write":
                if not denied(facts.action):
                    found.append(
                        f"{spec.id}: approved_write tool {name}'s action {facts.action}"
                        " must be agent: deny"
                    )
            elif not holdable(facts.action):
                found.append(
                    f"{spec.id}: {kind} tool {name}'s action {facts.action} is not agent-holdable"
                )
    # A denied action sits in task_scope only as an approved_write tool's own action.
    grant_actions = {tools[n].action for n in spec.tools.approved_write if n in tools}
    for action in sorted(spec.task_scope):
        if not holdable(action) and action not in grant_actions:
            found.append(f"{spec.id}: task scope may not include {action}")
    return found


class SpecV2Invalid(ValueError):
    pass


def _load() -> dict[str, AgentSpecV2]:
    loaded: dict[str, AgentSpecV2] = {}
    for agent_id, raw in SPECS_V2.items():
        found = AgentSpecV2.model_validate(raw)
        prompt(found.prompt)  # a spec names a registered prompt version
        grants = bool(found.tools.approved_write)
        problems = spec_problems(
            found,
            # An approved_write tool's action is `agent: deny` by design (only a person's grant
            # unlocks it); the codegen ties each denied scope action to one of the spec's
            # approved_write tools, so the loader lets a denied action through only then.
            holdable=lambda a, g=grants: agent_may_hold(a) or (g and agent_denied(a)),
        )
        if problems:
            raise SpecV2Invalid("; ".join(problems))
        loaded[agent_id] = found
    return loaded


AGENTS_V2: dict[str, AgentSpecV2] = _load()


def spec_v2(agent_id: str) -> AgentSpecV2:
    found = AGENTS_V2.get(agent_id)
    if found is None:
        raise LookupError(f"no v2 capability spec {agent_id!r}: capabilities run only from a spec")
    return found


__all__ = [
    "AGENTS_V2",
    "AgentSpecV2",
    "LimitsV2",
    "SpecV2Invalid",
    "ToolFacts",
    "ToolsByKind",
    "registry_problems",
    "spec_problems",
    "spec_v2",
]
