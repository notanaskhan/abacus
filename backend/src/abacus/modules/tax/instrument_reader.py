"""`tax.instrument_reader` v1: a trust's governing instrument to its seven tax determinations, with
clause citations (T-07-T13; TASK-8041; T-07 §6; SPEC-656 AC-1.4, AC-1.5, AC-2.1 to AC-2.4;
ADR-019, ADR-050, ADR-052, ADR-090; DEC-5027). Red zone (an agent path).

- **Consent first** (C19, AC-1.5): the trust (its entity with the tax year) must hold both §7216
  consents in force; without them the run is refused `consent_required` before any model call
  (and the route answers 409 before a run opens).
- **Inputs.** The run reads the clauses through `tax.read_instrument_clauses` (masked, wrapped as
  untrusted) and the facts through `tax.read_trust_facts`; both go to the model inside the
  untrusted block (the client's document is data, never instructions).
- **Code has the last word** (INV-2). A determination is kept only when its quote is verbatim in
  the clause it cites (a governed key without one is dropped and counted), and every figure in
  its text names a fact id whose amount it is. The kept ones go to C17's
  `tax.propose_trust_determinations`, which verifies each clause citation again through
  evidence (ADR-343) and writes only suggestions. The agent never adopts, approves or locks.
- **Workflow** `InstrumentReaderWorkflow` (ADR-090): wait for the instrument's text (the
  segmentation exists), read, judge, settle, propose; each step an activity, idempotent on the
  run; `workflow.patched` guards later changes.
- **Attribution.** The proposal is the run's: "<initiator> via Agent".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Annotated, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext, AuthContext

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes

CAPABILITY: Final = "tax.instrument_reader"
READ_CLAUSES: Final = "tax.read_instrument_clauses"
READ_FACTS: Final = "tax.read_trust_facts"
PROPOSE: Final = "tax.propose_trust_determinations"
MAX_CLAUSES: Final = 80
MAX_CLAUSE_CHARS: Final = 4000
GOVERNED: Final = frozenset(
    {"grantor_status", "trust_type", "fai_definition", "trustee_fees", "principal_invaded"}
)
Int = classified("internal")
Tri = classified("restricted", tri=True)
_FIGURE: Final = re.compile(r"(?<![A-Za-z])\$?\d[\d,]*(?:\.\d+)?")
_SHORT: Final = timedelta(seconds=30)
_TIMEOUT: Final = timedelta(seconds=150)
_RETRY: Final = RetryPolicy(maximum_attempts=3)


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class InstrumentClause(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Field(min_length=1, max_length=40), Int]
    label: Annotated[str, Field(min_length=1, max_length=40), Int]
    text: Annotated[str, Field(min_length=1, max_length=MAX_CLAUSE_CHARS), Tri]


class TrustFact(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Field(min_length=1, max_length=80), Int]
    label: Annotated[str, Field(max_length=120), Tri]
    amount: Annotated[str, Field(max_length=24), Tri]


class ReadInstrumentInput(BaseModel):
    """What the model is given: the masked clauses and the trust's code facts, nothing else."""

    model_config = _cfg()

    clauses: Annotated[list[InstrumentClause], Field(min_length=1, max_length=MAX_CLAUSES), Tri]
    facts: Annotated[list[TrustFact], Field(max_length=200), Tri] = []


class DeterminationAnswer(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(max_length=40), Int]
    value_code: Annotated[str, Field(min_length=1, max_length=60), Tri]
    value_text: Annotated[str, Field(min_length=1, max_length=300), Tri]
    clause_id: Annotated[str | None, Field(max_length=40), Int] = None
    quote: Annotated[str | None, Field(max_length=2000), Tri] = None
    fact_ids: Annotated[list[str], Field(max_length=20), Int] = []


class ReadInstrumentOutput(BaseModel):
    """The model's reading. No action field: the output can only become a proposal."""

    model_config = _cfg()

    determinations: Annotated[list[DeterminationAnswer], Field(max_length=7), Tri]


@dataclass(frozen=True)
class Settled:
    kept: tuple[DeterminationAnswer, ...]
    dropped_uncited: int
    dropped_numbers: int


def _fold(text: str) -> str:
    return " ".join(text.split())


def settle(answer: ReadInstrumentOutput, given: ReadInstrumentInput) -> Settled:
    """Code's verdict on the model's reading (INV-2): a governed key needs a verbatim quote in the
    clause it cites; every figure in the text must be a named fact's amount."""
    clauses = {c.id: _fold(c.text) for c in given.clauses}
    facts = {f.id: f.amount.replace(",", "") for f in given.facts}
    kept: list[DeterminationAnswer] = []
    uncited = numbers = 0
    seen: set[str] = set()
    for d in answer.determinations:
        if d.key in seen:
            continue
        cited = (
            d.clause_id is not None
            and d.quote is not None
            and _fold(d.quote) != ""
            and _fold(d.quote) in clauses.get(d.clause_id, "")
        )
        if d.key in GOVERNED and not cited:
            uncited += 1
            continue
        named = {facts[f] for f in d.fact_ids if f in facts}
        figures = [m.strip("$").replace(",", "") for m in _FIGURE.findall(d.value_text)]
        if any(f not in named for f in figures) or set(d.fact_ids) - facts.keys():
            numbers += 1
            continue
        seen.add(d.key)
        kept.append(d)
    return Settled(tuple(kept), uncited, numbers)


class ConsentRequired(DomainConflict):
    """C19 (AC-1.5): the trust lacks a §7216 consent in force for the year; nothing ran."""

    code = "consent_required"


@dataclass(frozen=True)
class ReaderResult:
    outcome: str  # proposed · nothing_to_propose · refused
    proposal_id: UUID | None
    code: str | None = None
    settled: Settled | None = None


async def _consents(agent: AgentContext, client_entity_id: UUID, tax_year: int) -> bool:
    from abacus.kernel.clock import now
    from abacus.modules.organisations.api import TriSubject, covering_consents

    found = await covering_consents(
        agent.tenant, [TriSubject(client_entity_id, tax_year)], await now(agent.tenant)
    )
    return found is not None


async def _judge(
    agent: AgentContext, given: ReadInstrumentInput, client_entity_id: UUID, tax_year: int
) -> ReadInstrumentOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, DataSubject, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("clauses", "facts"))  # the client's instrument
        .subjects(DataSubject(client_entity_id, tax_year))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=ReadInstrumentOutput,
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
    except Exception:  # a refused call (boundary, budget, schema): nothing is proposed
        return None
    return cast(ReadInstrumentOutput, result.output)


async def _tool(agent: AgentContext, step: int, name: str, arguments: dict[str, object]) -> object:
    from abacus.modules.agents.api import ToolCallIn, call_tool

    called = await call_tool(
        agent,
        ToolCallIn(
            run_id=agent.agent_run_id, step_seq=step, attempt=1, name=name, arguments=arguments
        ),
    )
    if not called.ok:
        raise LookupError(name)
    return called.result


async def read_instrument(
    agent: AgentContext, client_entity_id: UUID, tax_year: int
) -> ReaderResult:
    """One run: consent, the clauses and facts through C17, the model's reading settled by
    code, one proposal through C17."""
    if not await _consents(agent, client_entity_id, tax_year):
        return ReaderResult("refused", None, "consent_required")  # before any model call
    target: dict[str, object] = {"client_entity_id": str(client_entity_id), "tax_year": tax_year}
    try:
        clauses = cast(dict[str, object], await _tool(agent, 1, READ_CLAUSES, target))
        facts = cast(dict[str, object], await _tool(agent, 2, READ_FACTS, target))
    except LookupError:
        return ReaderResult("refused", None, "tool_refused")
    rows = [
        cast(dict[str, object], c)
        for c in cast(list[object], clauses.get("clauses", []))
        if isinstance(c, dict) and cast(dict[str, object], c).get("text")
    ]
    if not rows:
        return ReaderResult("nothing_to_propose", None, "not_segmented")
    given = ReadInstrumentInput(
        clauses=[
            InstrumentClause(
                id=str(r["id"]), label=str(r["label"]),
                text=str(r["text"])[:MAX_CLAUSE_CHARS],
            )
            for r in rows[:MAX_CLAUSES]
        ],
        facts=[
            TrustFact(id=str(f["id"]), label=str(f.get("label", "")), amount=str(f["amount"]))
            for f in cast(
                list[dict[str, object]],
                [*cast(list[object], facts.get("distributions", [])),
                 *cast(list[object], facts.get("expenses", []))],
            )
        ],
    )  # fmt: skip
    answer = await _judge(agent, given, client_entity_id, tax_year)
    if answer is None:
        return ReaderResult("refused", None, "model_refused")
    settled = settle(answer, given)
    if not settled.kept:
        return ReaderResult("nothing_to_propose", None, None, settled)
    try:
        proposed = cast(
            dict[str, object],
            await _tool(
                agent,
                3,
                PROPOSE,
                {
                    **target,
                    "determinations": [
                        {
                            "key": d.key,
                            "value_code": d.value_code,
                            "value_text": d.value_text,
                            "clauses": (
                                [{"clause_id": d.clause_id, "quote": d.quote}]
                                if d.clause_id is not None and d.quote is not None
                                else []
                            ),
                            "fact_ids": d.fact_ids,
                        }
                        for d in settled.kept
                    ],
                },
            ),
        )
    except LookupError:
        return ReaderResult("refused", None, "proposal_refused", settled)
    return ReaderResult("proposed", UUID(str(proposed["proposal_id"])), None, settled)


# --- the workflow (ADR-090) ---------------------------------------------------------------------


@dataclass(frozen=True)
class ReaderRunInput:
    tenant_id: str
    run_id: str
    return_id: str
    client_entity_id: str
    tax_year: int


@dataclass(frozen=True)
class ReaderRunOutcome:
    outcome: str
    code: str | None = None
    proposal_id: str | None = None


def reader_workflow_id(tenant_id: str, run_id: str) -> str:
    return f"instrument-reader:{tenant_id}:{run_id}"


@workflow.defn(name="InstrumentReaderWorkflow")
class InstrumentReaderWorkflow:
    """The run's state, then one activity (read, judge, settle, propose); a missing consent or
    a refused step ends the run failed with its code; the person asks again."""

    async def _state(self, p: ReaderRunInput, state: str, reason: str | None) -> None:
        await workflow.execute_activity(
            "agents.run_v2.set_state",
            args=[p.tenant_id, p.run_id, state, reason, None],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, p: ReaderRunInput) -> str:
        await self._state(p, "running", None)
        outcome = await workflow.execute_activity(
            "tax.instrument_reader.read",
            p,
            result_type=ReaderRunOutcome,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if outcome.outcome == "refused":
            await self._state(p, "failed", outcome.code or "refused")
            return "failed"
        await self._state(p, "succeeded", None)
        return outcome.outcome


@activity.defn(name="tax.instrument_reader.read")
async def read_activity(p: ReaderRunInput) -> ReaderRunOutcome:
    from abacus.modules.agents.api import AgentRunNotRunning, load_run_v2_context

    try:
        agent = await load_run_v2_context(UUID(p.tenant_id), UUID(p.run_id))
    except AgentRunNotRunning:
        return ReaderRunOutcome("refused", "run_ended")
    result = await read_instrument(agent, UUID(p.client_entity_id), p.tax_year)
    return ReaderRunOutcome(
        result.outcome, result.code, str(result.proposal_id) if result.proposal_id else None
    )


WORKFLOWS: dict[type, WorkClass] = {InstrumentReaderWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (read_activity,)


async def start_read(ctx: AuthContext, return_id: UUID) -> UUID:
    """`POST …/instrument/read`: the person starts the reader (AC-1.4). Refused before a run opens
    when the trust lacks a §7216 consent (409 `consent_required`) or its instrument is not
    segmented (409 `not_segmented`)."""
    from sqlalchemy import text

    from abacus.kernel.clock import now
    from abacus.kernel.db import tenant_session
    from abacus.kernel.errors import NotFound
    from abacus.modules.agents.api import open_capability_run
    from abacus.modules.organisations.api import TriSubject, covering_consents
    from abacus.modules.tax.fiduciary_contract import NotSegmented

    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT r.engagement_id, r.client_entity_id, r.tax_year, s.status "
                    "FROM tax_returns r LEFT JOIN instrument_interpretations i "
                    "ON i.work_item_id = r.work_item_id AND i.superseded_at IS NULL "
                    "LEFT JOIN instrument_segmentations s ON s.id = i.segmentation_id "
                    "WHERE r.work_item_id = :r"
                ),
                {"r": return_id},
            )
        ).first()
    if row is None or row.client_entity_id is None:
        raise NotFound("tax_return")
    consents = await covering_consents(
        ctx.tenant, [TriSubject(row.client_entity_id, row.tax_year)], await now(ctx.tenant)
    )
    if consents is None:
        raise ConsentRequired(facts={"client_entity_id": str(row.client_entity_id)})
    if row.status != "segmented":
        raise NotSegmented(facts={"status": row.status or "none"})
    run_id = await open_capability_run(
        ctx,
        agent_id=CAPABILITY,
        engagement_id=row.engagement_id,
        inputs={"client_entity_id": str(row.client_entity_id), "tax_year": row.tax_year},
        work_item_ref=f"tax_return:{return_id}",
    )
    await dispatch(
        InstrumentReaderWorkflow,
        ReaderRunInput(
            str(ctx.tenant_id),
            str(run_id),
            str(return_id),
            str(row.client_entity_id),
            row.tax_year,
        ),
        id=reader_workflow_id(str(ctx.tenant_id), str(run_id)),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


__all__ = [
    "ACTIVITIES",
    "CAPABILITY",
    "WORKFLOWS",
    "InstrumentReaderWorkflow",
    "ReadInstrumentInput",
    "ReadInstrumentOutput",
    "read_activity",
    "read_instrument",
    "settle",
    "start_read",
]
