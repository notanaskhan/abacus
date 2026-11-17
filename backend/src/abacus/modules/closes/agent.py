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
- `flux` (C-01-T30): a flux line's explanation. Code offers the line's change and the month's
  register lines (current lines as they are, the prior month's with the sign reversed) as money
  facts; the model groups them into drivers (`drivers`, fact ids only, never an amount). Code sums
  each driver and the drivers must **foot to the change** (`drivers_do_not_foot`); the runner asks
  once more with `repair`, then the run waits on a person (`closes.agent_runs`).
- `planner` (C-01-T30): a close plan draft. Code profiles 14 months of the entity's closes and
  offers each balance-sheet account its closed procedure and source sets (`choices`); the model
  picks one of each per row (`rows`) or leaves the row out. Every row lands as a suggestion a
  person adopts (AC-22).

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
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict
from abacus.modules.identity.api import AgentContext

CAPABILITY: Final = "close.agent"
Mode = Literal["run", "intake", "bank_rec", "aje", "flux", "planner"]
MODES: Final[tuple[Mode, ...]] = ("run", "intake", "bank_rec", "aje", "flux", "planner")
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
# `trial_balance.read`: C-01-T30 (DEC-5413), so the run's `ledger_line` citations to register
# lines verify (the citable authorises the actor on the engagement before it reads a line).
TASK_SCOPE: Final = frozenset(
    {
        "close.read",
        "suggestion.create",
        "issue.create",
        "decision_card.raise",
        "trial_balance.read",
    }
)
MAX_DRIVERS: Final = 8
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


class PlanChoiceIn(BaseModel):
    """One account the planner may plan: code's closed sets for it (procedures, sources)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_key: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"), Int]
    procedures: Annotated[list[str], Field(min_length=1, max_length=13), Int]
    sources: Annotated[list[str], Field(min_length=1, max_length=5), Int]


class CloseAgentInput(BaseModel):
    """What the model sees: the mode, code's facts, the citations code verified, the options code
    offers, and the untrusted client text (never instructions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Annotated[Mode, Int]
    close_id: Annotated[UUID, Int]
    facts: Annotated[list[FactIn], Field(max_length=200), Int]
    citations: Annotated[list[UUID], Field(max_length=200), Int] = []
    options: Annotated[list[str], Field(max_length=20), Int] = []
    untrusted: Annotated[list[str], Field(max_length=250), Conf] = []
    choices: Annotated[list[PlanChoiceIn], Field(max_length=120), Int] = []
    repair: Annotated[Literal["drivers_do_not_foot"] | None, Int] = None


class DriverOut(BaseModel):
    """A flux driver: a short label (no figure) and the fact ids code sums (C-01 AC-49)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[^0-9]*$"), Conf]
    fact_ids: Annotated[list[str], Field(min_length=1, max_length=40), Int]


class PlanRowOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row_key: Annotated[str, Field(max_length=64), Int]
    procedure: Annotated[str, Field(max_length=40), Int]
    source: Annotated[str, Field(max_length=40), Int]


class CloseAgentOutput(BaseModel):
    """The model's answer: AgentBlocks (`blocks`), and, where code offered options, one of them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks: Annotated[dict[str, object], Conf]
    option: Annotated[str | None, Field(max_length=80), Int] = None
    drivers: Annotated[list[DriverOut], Field(max_length=MAX_DRIVERS), Int] = []
    rows: Annotated[list[PlanRowOut], Field(max_length=120), Int] = []


@dataclass(frozen=True)
class Driver:
    label: str
    fact_ids: tuple[str, ...]
    amount: Decimal  # code's sum of the facts


@dataclass(frozen=True)
class Settled:
    mode: Mode
    blocks: object  # agents.blocks.AgentBlocks
    option: str | None
    drivers: tuple[Driver, ...] = ()
    rows: tuple[PlanRowOut, ...] = ()


def _money(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation:
        raise OutputRefused(facts={"reason": "fact_not_money"}) from None


def settle_drivers(given: CloseAgentInput, answer: CloseAgentOutput) -> tuple[Driver, ...]:
    """Flux: each driver's facts are the offered line facts (each used once), code sums them, and
    the drivers foot to the `change` fact exactly (else `drivers_do_not_foot`)."""
    facts = {f.id: f for f in given.facts}
    change = facts.get("change")
    if change is None or not answer.drivers:
        raise OutputRefused(facts={"reason": "drivers_required"})
    used: set[str] = set()
    out: list[Driver] = []
    for d in answer.drivers:
        total = Decimal(0)
        for fid in d.fact_ids:
            fact = facts.get(fid)
            if fact is None or fact.kind != "money" or fid[:1] not in ("c", "p") or fid in used:
                raise OutputRefused(facts={"reason": "driver_fact_not_offered"})
            used.add(fid)
            total += _money(fact.value)
        out.append(Driver(d.label.strip(), tuple(d.fact_ids), total))
    if sum((d.amount for d in out), Decimal(0)) != _money(change.value):
        raise OutputRefused(facts={"reason": "drivers_do_not_foot"})
    return tuple(out)


def settle_rows(given: CloseAgentInput, answer: CloseAgentOutput) -> tuple[PlanRowOut, ...]:
    """Planner: a row only for an offered account, once, with one of its procedures and one of
    its sources; an account left out stays unplanned (the person adds it)."""
    choices = {c.row_key: c for c in given.choices}
    seen: set[str] = set()
    for row in answer.rows:
        choice = choices.get(row.row_key)
        if (
            choice is None
            or row.row_key in seen
            or row.procedure not in choice.procedures
            or row.source not in choice.sources
        ):
            raise OutputRefused(facts={"reason": "option_not_offered"})
        seen.add(row.row_key)
    if not answer.rows:
        raise OutputRefused(facts={"reason": "rows_required"})
    return tuple(answer.rows)


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
    if given.mode != "flux" and answer.drivers:
        raise OutputRefused(facts={"reason": "drivers_outside_flux"})
    if given.mode != "planner" and answer.rows:
        raise OutputRefused(facts={"reason": "rows_outside_planner"})
    drivers = settle_drivers(given, answer) if given.mode == "flux" else ()
    rows = settle_rows(given, answer) if given.mode == "planner" else ()
    return Settled(given.mode, blocks, answer.option, drivers, rows)


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
    # Payroll +7,670 (12.5%) = 4,350 + 1,850 + 1,470 (the figure book): the scenario's register
    # facts c1 (two new hires), c2 (the bonus run) and c3 (overtime).
    "flux": CloseAgentOutput(
        blocks={
            "version": 1,
            "parts": [
                _p(
                    _t("Payroll rose "),
                    _f("change"),
                    _t(" on two new hires, the bonus run and overtime during the install."),
                )
            ],
        },
        drivers=[
            DriverOut(label="Two new hires", fact_ids=["c1"]),
            DriverOut(label="Bonus run", fact_ids=["c2"]),
            DriverOut(label="Overtime during the roaster install", fact_ids=["c3"]),
        ],
    ),
    "planner": CloseAgentOutput(
        blocks={
            "version": 1,
            "parts": [
                _p(
                    _t("Drafted from "),
                    _f("months"),
                    _t(" months of closes over "),
                    _f("accounts"),
                    _t(" balance sheet accounts."),
                )
            ],
        },
        rows=[
            PlanRowOut(row_key="1000", procedure="reconciliation", source="bank_feed"),
            PlanRowOut(row_key="1350", procedure="amortization", source="accrued_register"),
        ],
    ),
}
