"""`tax.return_analyst` v1 modes `k1_treatments` and `residency` (T-04-T38; T-04 §6; SPEC-649 §3.7,
§3.8; ADR-005, ADR-050; DEC-4410). Red zone (an agent path).

Code computes; the model explains; a person decides. Neither mode can confirm, approve or send: the
capability's task scope holds `proposal.create` only, and its tools are reads, code's computes and
the two propose tools.

- **k1_treatments.** Through C17 (so §7216 consent gates the first read): the return's K-1
  activities and their treatments with code's resolved values and SALY. The model writes each
  treatment's rationale (`tax.return_analyst.k1_treatments@v1`); code keeps sentences whose numbers
  are code's own and never changes a resolved value. The still-proposed treatments become one
  `pass_through_treatments` proposal through `tax.propose_pass_through_treatments` carrying code's
  resolved values only (Ridgeline: seven, treatment 8 already approved).
- **residency.** Through C17: code's rules (`tax.compute_residency_facts`) over the facts the
  determination holds (T-04-T39) give the recommendation and the conflict; the model writes the
  rationale (`tax.return_analyst.residency@v1`) and never picks another option. A conflict answers
  `action_required` with an internal client-question draft in template words
  (`residency_service.client_question`), never sent: a reviewer sends it. The recommendation is one
  `residency` proposal through `tax.propose_residency` (the 150-day variant: option 2,
  full-year State and part-year City).
- **Runs.** `AnalystModeWorkflow` (one activity), started from TXI-02's `…/treatment-runs` and
  TXI-03's `…/residency/proposal-runs` by a person (`open_capability_run`), runs as that person's
  agent ("<person> via Agent").
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext, AuthContext

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
    from abacus.modules.tax.fix_runner import numbers_in

ANALYST: Final = "tax.return_analyst"
K1_PROMPT: Final = "tax.return_analyst.k1_treatments@v1"
RESIDENCY_PROMPT: Final = "tax.return_analyst.residency@v1"
# What the modes may never do (the reviewer's and the person's actions, ADR-005).
NEVER: Final = frozenset(
    {
        "k1_treatment.approve",
        "k1_treatment.override",
        "residency.confirm",
        "issue.send_to_client",
        "proposal.approve",
        "tax_return.approve",
    }
)
Int = classified("internal")
Tri = classified("restricted", tri=True)
_SENTENCE: Final = re.compile(r"(?<=[.!?])\s+")


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TreatmentRationale(BaseModel):
    model_config = _cfg()

    kind: Annotated[str, Field(min_length=1, max_length=60), Int]
    rationale: Annotated[str, Field(min_length=1, max_length=600), Tri]
    citation_ids: Annotated[list[UUID], Field(max_length=10), Int] = []


class K1TreatmentsOutput(BaseModel):
    """`tax.return_analyst.k1_treatments@v1`'s answer: rationale per treatment, nothing else."""

    model_config = _cfg()

    treatments: Annotated[list[TreatmentRationale], Field(max_length=20), Tri]


class ResidencyOutput(BaseModel):
    """`tax.return_analyst.residency@v1`'s answer: the rationale and its citations."""

    model_config = _cfg()

    rationale: Annotated[str, Field(min_length=1, max_length=1200), Tri]
    citation_ids: Annotated[list[UUID], Field(max_length=10), Int] = []


@dataclass(frozen=True)
class K1Fact:
    treatment_id: UUID
    kind: str
    status: str
    resolved: str | None
    prior: str | None
    changed: bool


def keep_sentences(text: str, allowed: frozenset[Decimal]) -> str:
    """Code's last word on model text: only sentences whose every number is one of code's."""
    kept = [s for s in _SENTENCE.split(text.strip()) if s and numbers_in(s) <= allowed]
    return " ".join(kept)


def _allowed(facts: Sequence[K1Fact]) -> frozenset[Decimal]:
    found: set[Decimal] = {Decimal(2024), Decimal(2025)}
    for f in facts:
        for value in (f.resolved, f.prior):
            if value:
                found |= numbers_in(value)
    return frozenset(found)


def settle_k1(
    answer: K1TreatmentsOutput | None, facts: Sequence[K1Fact], cited: frozenset[UUID]
) -> dict[str, tuple[str, tuple[UUID, ...]]]:
    """Per kind: the kept rationale and its verified citations (code's sentence when nothing
    stands). Resolved values are never taken from the model."""
    allowed = _allowed(facts)
    by_kind = {t.kind: t for t in (answer.treatments if answer is not None else [])}
    out: dict[str, tuple[str, tuple[UUID, ...]]] = {}
    for f in facts:
        given = by_kind.get(f.kind)
        text = keep_sentences(given.rationale, allowed) if given is not None else ""
        ids = tuple(c for c in (given.citation_ids if given else []) if c in cited)
        if not text:
            change = f" (was {f.prior})" if f.changed and f.prior else ""
            text = (
                f"{f.kind.replace('_', ' ').capitalize()}: {f.resolved or 'unresolved'}{change}."
            )
        out[f.kind] = (text, ids)
    return out


@dataclass(frozen=True)
class ModeResult:
    outcome: str  # proposed · action_required · nothing_to_propose · waiting_on_inputs · refused
    proposal_id: UUID | None = None
    proposed: int = 0
    recommended: str | None = None
    rationale: Mapping[str, tuple[str, tuple[UUID, ...]]] | None = None
    client_question: tuple[str, str] | None = None
    code: str | None = None


async def _judge(
    agent: AgentContext,
    prompt: str,
    task: Mapping[str, object],
    output: type[BaseModel],
    entity: UUID,
    year: int,
) -> BaseModel | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.ai_gateway.context import DataSubject
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(ANALYST)
    context = (
        ContextBuilder()
        .task(dict(task), untrusted=("facts",))
        .subjects(DataSubject(entity, year))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=prompt,
                tier=spec.tier,
                output_schema=output,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant, agent.engagement_id, ANALYST, agent.agent_run_id
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
    except Exception:  # a refused call: code's own sentences stand
        return None
    return cast(BaseModel, result.output)


class _Tools:
    """The mode's C17 calls, numbered in order (the step sequence of the run)."""

    def __init__(self, agent: AgentContext) -> None:
        self.agent = agent
        self.seq = 0

    async def __call__(self, name: str, arguments: dict[str, object]):  # noqa: ANN204 -- ToolOutcome
        from abacus.modules.agents.api import ToolCallIn, call_tool

        self.seq += 1
        return await call_tool(
            self.agent,
            ToolCallIn(
                run_id=self.agent.agent_run_id,
                step_seq=self.seq,
                attempt=1,
                name=name,
                arguments=arguments,
            ),
        )


async def k1_treatments_mode(agent: AgentContext, entity: UUID, year: int) -> ModeResult:
    """The `k1_treatments` mode (module docstring)."""
    tool = _Tools(agent)
    taxpayer: dict[str, object] = {"client_entity_id": str(entity), "tax_year": year}
    read = await tool("tax.read_prior_year", taxpayer)
    if not read.ok:
        if read.code == "consent_required":
            return ModeResult("waiting_on_inputs", code=read.code)
        return ModeResult("refused", code=read.code)
    rows = cast(list[dict[str, object]], cast(dict[str, object], read.result)["treatments"])
    facts = [
        K1Fact(
            UUID(str(r["id"])),
            str(r["kind"]),
            str(r["status"]),
            cast(str | None, r.get("resolved_text")),
            cast(str | None, r.get("prior_text")),
            bool(r.get("changed")),
        )
        for r in rows
    ]
    pending = [f for f in facts if f.status == "proposed" and f.resolved]
    if not pending:
        return ModeResult("nothing_to_propose")
    task = {
        "facts": [
            {"kind": f.kind, "resolved": f.resolved, "saly": f.prior, "changed": f.changed}
            for f in facts
        ]
    }
    answer = cast(
        K1TreatmentsOutput | None,
        await _judge(agent, K1_PROMPT, task, K1TreatmentsOutput, entity, year),
    )
    rationale = settle_k1(answer, facts, frozenset())
    proposed = await tool(
        "tax.propose_pass_through_treatments",
        {
            **taxpayer,
            "changes": [
                {"treatment_id": str(f.treatment_id), "treatment": f.resolved} for f in pending
            ],
        },
    )
    if not proposed.ok:
        return ModeResult("refused", rationale=rationale, code=proposed.code)
    proposal = UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    return ModeResult("proposed", proposal, len(pending), rationale=rationale)


async def residency_mode(
    agent: AgentContext, entity: UUID, year: int, return_id: UUID
) -> ModeResult:
    """The `residency` mode (module docstring)."""
    from abacus.modules.tax import residency_service as rs

    tool = _Tools(agent)
    taxpayer: dict[str, object] = {"client_entity_id": str(entity), "tax_year": year}
    gate = await tool("tax.read_return", taxpayer)  # §7216 before any residency fact is read
    if not gate.ok:
        if gate.code == "consent_required":
            return ModeResult("waiting_on_inputs", code=gate.code)
        return ModeResult("refused", code=gate.code)
    found = await rs.determination(agent.tenant, return_id)
    if found is None:
        return ModeResult("nothing_to_propose", code="no_determination")
    view = await rs.residency_view(cast("AuthContext", agent), return_id)
    facts = [
        rs.Fact(
            cast(rs.FactKey, f.key),
            f.value,
            f.citation_ids,
            cast(rs.SourceKind, f.source_kind),
        )
        for f in view.facts
    ]
    inputs = rs.residency_inputs(facts)
    computed = await tool(
        "tax.compute_residency_facts",
        {
            **taxpayer,
            "nyc_days": inputs.nyc_days,
            "has_nyc_abode": inputs.has_nyc_abode,
            "main_home_outside_nyc": inputs.main_home_outside_nyc,
        },
    )
    if not computed.ok:
        return ModeResult("refused", code=computed.code)
    result = cast(dict[str, object], computed.result)
    recommended = str(result["recommended"])
    conflict = bool(result["conflict"])
    cited = frozenset(c for f in view.facts for c in f.citation_ids)
    task = {
        "facts": [{"key": f.key, "value": dict(f.value)} for f in view.facts],
        "options": [o.key for o in rs.OPTIONS],
        "recommended": recommended,
        "conflict": conflict,
    }
    answer = cast(
        ResidencyOutput | None,
        await _judge(agent, RESIDENCY_PROMPT, task, ResidencyOutput, entity, year),
    )
    allowed = frozenset({Decimal(inputs.nyc_days), Decimal(year)})
    text = keep_sentences(answer.rationale, allowed) if answer is not None else ""
    ids = tuple(c for c in (answer.citation_ids if answer else []) if c in cited)
    rationale = {"residency": (text or f"Code recommends {recommended}.", ids)}
    proposed = await tool(
        "tax.propose_residency",
        {**taxpayer, "determination_id": str(found.id), "option": recommended},
    )
    if not proposed.ok:
        return ModeResult("refused", recommended=recommended, code=proposed.code)
    proposal = UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    question = rs.client_question(cast("rs.ResidencyOption", recommended)) if conflict else None
    return ModeResult(
        "action_required" if conflict else "proposed",
        proposal,
        1,
        recommended=recommended,
        rationale=rationale,
        client_question=question,
    )


# --- AnalystModeWorkflow -------------------------------------------------------------------------

_TIMEOUT: Final = timedelta(minutes=3)
_SHORT: Final = timedelta(seconds=30)
_RETRY: Final = RetryPolicy(maximum_attempts=3)


@dataclass(frozen=True)
class ModeRunInput:
    tenant_id: str
    run_id: str
    mode: str  # k1_treatments · residency
    client_entity_id: str
    tax_year: int
    return_id: str


@dataclass(frozen=True)
class ModeRunOutcome:
    outcome: str
    proposal_id: str | None = None
    proposed: int = 0
    recommended: str | None = None
    code: str | None = None


def mode_workflow_id(tenant_id: str, run_id: str) -> str:
    return f"analyst-mode:{tenant_id}:{run_id}"


@workflow.defn(name="AnalystModeWorkflow")
class AnalystModeWorkflow:
    """One activity; a missing consent or a refused tool ends the run failed (a person asks
    again once the consent is recorded)."""

    async def _state(self, p: ModeRunInput, state: str, reason: str | None) -> None:
        await workflow.execute_activity(
            "agents.run_v2.set_state",
            args=[p.tenant_id, p.run_id, state, reason, None],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, p: ModeRunInput) -> str:
        await self._state(p, "running", None)
        outcome = await workflow.execute_activity(
            "tax.analyst_mode.run",
            p,
            result_type=ModeRunOutcome,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if outcome.outcome in ("refused", "waiting_on_inputs"):
            await self._state(p, "failed", outcome.code or outcome.outcome)
            return "failed"
        await self._state(p, "succeeded", None)
        return outcome.outcome


@activity.defn(name="tax.analyst_mode.run")
async def mode_activity(p: ModeRunInput) -> ModeRunOutcome:
    from abacus.modules.agents.api import AgentRunNotRunning, load_run_v2_context

    try:
        agent = await load_run_v2_context(UUID(p.tenant_id), UUID(p.run_id))
    except AgentRunNotRunning:
        return ModeRunOutcome("refused", code="run_ended")
    entity, year = UUID(p.client_entity_id), p.tax_year
    if p.mode == "k1_treatments":
        result = await k1_treatments_mode(agent, entity, year)
    elif p.mode == "residency":
        result = await residency_mode(agent, entity, year, UUID(p.return_id))
    else:
        return ModeRunOutcome("refused", code="mode_unknown")
    return ModeRunOutcome(
        result.outcome,
        str(result.proposal_id) if result.proposal_id else None,
        result.proposed,
        result.recommended,
        result.code,
    )


WORKFLOWS: dict[type, WorkClass] = {AnalystModeWorkflow: "interactive"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (mode_activity,)


async def start_mode(
    ctx: AuthContext, mode: str, return_id: UUID, entity: UUID, year: int, engagement: UUID
) -> UUID:
    """A person starts a mode on a return (TXI-02's treatment run, TXI-03's proposal run)."""
    from abacus.modules.agents.api import open_capability_run

    run_id = await open_capability_run(
        ctx,
        agent_id=ANALYST,
        engagement_id=engagement,
        inputs={
            "mode": mode,
            "return_id": str(return_id),
            "client_entity_id": str(entity),
            "tax_year": year,
        },
        work_item_ref=f"tax_return:{return_id}",
    )
    await dispatch(
        AnalystModeWorkflow,
        ModeRunInput(str(ctx.tenant_id), str(run_id), mode, str(entity), year, str(return_id)),
        id=mode_workflow_id(str(ctx.tenant_id), str(run_id)),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


async def return_facts(ctx: AuthContext, return_id: UUID) -> tuple[UUID, UUID, int]:
    """(engagement, filing entity, tax year) of a return the caller may read (404 otherwise)."""
    from sqlalchemy import text

    from abacus.kernel.db import tenant_session
    from abacus.kernel.errors import NotFound
    from abacus.modules.engagements.api import get_ref, work_item_engagement

    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")
    await get_ref(ctx, engagement)  # a wall answers 404
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT client_entity_id, tax_year FROM tax_returns WHERE work_item_id = :r"),
                {"r": return_id},
            )
        ).first()
    if row is None or row.client_entity_id is None:
        raise NotFound("tax_return")
    return engagement, cast(UUID, row.client_entity_id), int(row.tax_year)


async def activity_return(ctx: AuthContext, activity_id: UUID) -> UUID:
    """The return a K-1 activity is on (404 when the caller cannot read it)."""
    from sqlalchemy import text

    from abacus.kernel.db import tenant_session
    from abacus.kernel.errors import NotFound

    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT tax_return_id FROM k1_activities WHERE id = :a"), {"a": activity_id}
        )
    if found is None:
        raise NotFound("k1_activity")
    return cast(UUID, found)


__all__ = [
    "ACTIVITIES",
    "ANALYST",
    "NEVER",
    "WORKFLOWS",
    "AnalystModeWorkflow",
    "K1Fact",
    "K1TreatmentsOutput",
    "ModeResult",
    "ResidencyOutput",
    "activity_return",
    "k1_treatments_mode",
    "keep_sentences",
    "residency_mode",
    "return_facts",
    "settle_k1",
    "start_mode",
]
