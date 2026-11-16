"""`close.agent` v1, the close engine's one capability (C-01-T29; C-01 §5; chapter 05 §5.3.3;
ADR-005, ADR-050, ADR-115; red).

Spec: `agents/specs/v2/close.agent.yaml` (shape `workflow`; task scope `close.read`,
`suggestion.create`, `issue.create`, `decision_card.raise`; no TRI). Four modes, one registered
prompt each (`close.agent.<mode>@v1`), all on the frozen `evals/close_agent` suite (C-01-T31):

- `run`: the close run's sentences over the run's code facts; the plan is C-01's code plan
  provider (`closes.close_run`, `run_plan.close_run_plan`), never the model's.
- `intake`: the intake summary paragraph over an upload's code totals (`sheet_cell` citations).
- `bank_rec`: why an exception surfaced, over the reconciliation's code facts.
- `aje`: the reasoning for an AJE draft whose amount and debit account code chose.

**Every output is AgentBlocks** (`agents.blocks`): a sentence that carries a number references a
code fact (`fact` segment) or a verified citation; a bare figure, markup, a claimed human act or
an unknown fact id refuses the output (`settle`, number provenance, INV-2). The model answers
only from the closed option sets code offers (`CloseAgentOutput.option`, the AJE credit account
from the vendor's prior categorisations); anything else is refused. **Tools** outside the spec's
allow-list are refused `out_of_scope` (`scoped_tool`) before any handler runs (the runtime does
the same on its side). The model never computes a figure (ADR-050), never proposes or posts an
entry, never answers a decision card (INV-1).

Client uploads and client answers are untrusted inputs (ADR-052): they reach the model only
inside the context builder's untrusted section and never change the facts or the options. The
fake model's scenario responses for each mode live in `FAKE_RESPONSES` (CI and the demo never call
a provider).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict
from abacus.modules.identity.api import AgentContext

CAPABILITY: Final = "close.agent"
Mode = Literal["run", "intake", "bank_rec", "aje"]
MODES: Final[tuple[Mode, ...]] = ("run", "intake", "bank_rec", "aje")
PROMPTS: Final[Mapping[Mode, str]] = {mode: f"close.agent.{mode}@v1" for mode in MODES}
TOOLS: Final = frozenset(
    {
        "close.read_checklist",
        "close.read_register",
        "close.reconcile",
        "close.read_upload_table",
        "close.plan_history_profile",
        "close.propose_aje",
    }
)
TASK_SCOPE: Final = frozenset(
    {"close.read", "suggestion.create", "issue.create", "decision_card.raise"}
)
# The reserved acts no close.agent output may take or ask for (INV-1, DE-5) are C17's
# never-verbs, refused at tool registration (`agents.tools.registry.NEVER_TOOL_VERBS`) and by the
# matrix (`agent: deny`); the task scope above writes only a suggestion, an issue and a card.
Int = classified("internal")
Conf = classified("confidential")


class OutOfScope(DomainConflict):
    code = "out_of_scope"


class OutputRefused(DomainConflict):
    """The model's output may not be shown: `facts.reason` names why (a code, never the text)."""

    code = "agent_output_refused"


def scoped_tool(name: str) -> str:
    """The tool, when the capability may call it; any other is refused `out_of_scope`."""
    if name not in TOOLS:
        raise OutOfScope(facts={"tool": name[:80]})
    return name


class FactIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$"), Int]
    kind: Annotated[Literal["money", "count", "percent", "date", "number"], Int]
    value: Annotated[str, Field(max_length=40), Conf]
    basis: Annotated[str, Field(max_length=200), Int]


class CloseAgentInput(BaseModel):
    """What the model sees: the mode, code's facts, the citations code verified, the options code
    offers, and the untrusted client text (never instructions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Annotated[Mode, Int]
    close_id: Annotated[UUID, Int]
    facts: Annotated[list[FactIn], Field(max_length=200), Int]
    citations: Annotated[list[UUID], Field(max_length=200), Int] = []
    options: Annotated[list[str], Field(max_length=20), Int] = []
    untrusted: Annotated[list[str], Field(max_length=50), Conf] = []


class CloseAgentOutput(BaseModel):
    """The model's answer: AgentBlocks (`blocks`), and, where code offered options, one of them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks: Annotated[dict[str, object], Conf]
    option: Annotated[str | None, Field(max_length=80), Int] = None


@dataclass(frozen=True)
class Settled:
    mode: Mode
    blocks: object  # agents.blocks.AgentBlocks
    option: str | None


def settle(given: CloseAgentInput, answer: CloseAgentOutput) -> Settled:
    """Code settles the answer: blocks validate against the run's facts and verified citations
    (a number outside a fact token, an unknown fact or citation, markup or a claimed human act is
    refused), and the option must be one code offered."""
    from abacus.modules.agents.api import AgentFact, BlocksRejected, validate_blocks

    facts = {
        f.id: AgentFact(id=f.id, kind=f.kind, value=f.value, basis=f.basis) for f in given.facts
    }
    try:
        blocks = validate_blocks(answer.blocks, facts, frozenset(given.citations))
    except BlocksRejected as rejected:
        raise OutputRefused(facts={"reason": rejected.code}) from None
    if answer.option is not None and answer.option not in given.options:
        raise OutputRefused(facts={"reason": "option_not_offered"})
    if given.mode == "aje" and given.options and answer.option is None:
        raise OutputRefused(facts={"reason": "option_required"})
    return Settled(given.mode, blocks, answer.option)


async def answer(agent: AgentContext, given: CloseAgentInput) -> Settled:
    """One model call for the mode through the gateway (boundary, provider terms, budget), then
    `settle`. A refused call raises `OutputRefused` (nothing is shown)."""
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder().task(given.model_dump(mode="json"), untrusted=("untrusted",)).build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=PROMPTS[given.mode],
                tier=spec.tier,
                output_schema=CloseAgentOutput,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant, agent.engagement_id, CAPABILITY, agent.agent_run_id
                ),
                context=context,
                work_class=spec.work_class,
                essential=spec.essential,
                routes=spec.routes,
                cheaper_tiers=spec.cheaper_tiers,
                max_output_tokens=spec.limits.max_output_tokens,
                timeout_seconds=spec.limits.max_seconds,
            )
        )
    except Exception:  # boundary, budget or schema refusal: nothing is shown
        raise OutputRefused(facts={"reason": "gateway_refused"}) from None
    return settle(given, cast(CloseAgentOutput, result.output))


def run_plan_provider() -> str:
    """The run mode's plan: C-01's code plan provider (`closes.close_run`), never the model's."""
    from abacus.modules.closes.run_plan import PROVIDER

    return PROVIDER


def _p(*segments: dict[str, object]) -> dict[str, object]:
    return {"kind": "p", "segments": list(segments)}


def _t(text: str) -> dict[str, object]:
    return {"kind": "text", "text": text}


def _f(fact_id: str) -> dict[str, object]:
    return {"kind": "fact", "fact_id": fact_id}


# The fake model's scenario responses, one per mode (the Copperleaf figure book, C-01-T13): every
# figure is a fact token.
FAKE_RESPONSES: Final[Mapping[Mode, CloseAgentOutput]] = {
    "run": CloseAgentOutput(
        blocks={
            "version": 1,
            "parts": [
                _p(
                    _t("The run finished "),
                    _f("procedures_done"),
                    _t(" procedures; "),
                    _f("open_issues"),
                    _t(" exceptions are open for review."),
                )
            ],
        },
    ),
    "intake": CloseAgentOutput(
        blocks={
            "version": 1,
            "parts": [
                _p(
                    _t("The Square payouts report totals "),
                    _f("gross"),
                    _t(" gross, "),
                    _f("fees"),
                    _t(" in fees and "),
                    _f("net"),
                    _t(" net."),
                )
            ],
        },
    ),
    "bank_rec": CloseAgentOutput(
        blocks={
            "version": 1,
            "parts": [
                _p(
                    _t("This payment is "),
                    _f("amount"),
                    _t(" against a usual "),
                    _f("usual"),
                    _t(", a change of "),
                    _f("change_pct"),
                    _t("."),
                )
            ],
        },
    ),
    "aje": CloseAgentOutput(
        blocks={
            "version": 1,
            "parts": [
                _p(
                    _t("The vendor refund of "),
                    _f("amount"),
                    _t(
                        " was deposited but not recorded; the vendor's prior purchases were "
                        "categorised to the account chosen."
                    ),
                )
            ],
        },
        option="5010",
    ),
}
