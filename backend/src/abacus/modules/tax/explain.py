"""`tax.return_analyst` mode `explain` for a return's issue (T-04-T31; TASK-6819; DEC-3413; T-04
§6, AC-4.5; SHL-15 d; ADR-050, ADR-052). PROTECTED (tax agents).

"Explain…" on a return's issue (`POST /v1/issues/{id}/explanations`, `issue.explain`; review's
explainer slot for `tax_return`) opens the person's run of `tax.return_analyst` and dispatches
`IssueExplainWorkflow`. The run decides nothing and changes nothing:

1. `tax.read_return` under C19's §7216 gate (no consent: the run ends `waiting_on_inputs`).
2. `tax.list_documents`, then code's facts: each K-1 box on the return's documents that can bear
   on a tax-exempt-interest issue (`fix_runner.CITING_BOXES`), with its value as code read it.
3. Each fact's box cited as the agent on the issue's own anchor; only verified citations go on.
4. The model writes the explanation over those facts (`tax.return_analyst.explain@v1`,
   `ExplainOutput`), naming the citation ids it relies on.
5. Code keeps only the citations that verified and only the sentences whose numbers are code's
   facts (number provenance 1.0, DE-3); a model answer with nothing left falls back to code's own
   sentence over the facts. The text is stored sealed through `review.api.record_explanation`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
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
    from abacus.modules.tax.fix_runner import CITING_BOXES, numbers_in, parse_amount

ANALYST: Final = "tax.return_analyst"
PROMPT: Final = "tax.return_analyst.explain@v1"
Int = classified("internal")
Tri = classified("restricted")
_SENTENCE: Final = re.compile(r"(?<=[.!?])\s+")
BOX_LABELS: Final = {
    "k1_1065.box18a": "K-1 box 18A",
    "k1_1065.box18": "K-1 box 18",
    "k1_1120s.box16a": "K-1 box 16A",
    "k1_1120s.box16": "K-1 box 16",
}


class ExplainOutput(BaseModel):
    """`tax.return_analyst.explain@v1`'s answer: plain sentences and the citations they use."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=1200), Tri]
    citation_ids: Annotated[list[UUID], Field(max_length=10), Int]


class ExplainInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: Annotated[UUID, Int]
    client_entity_id: Annotated[UUID, Int]
    tax_year: Annotated[int, Field(ge=2000, le=2100), Int]


@dataclass(frozen=True)
class Fact:
    citation_id: UUID
    label: str
    value: str  # as code read it from the box


def _structural(year: int) -> frozenset[Decimal]:
    """The numbers that name things rather than state amounts: the tax year, and the form, box
    and line numbers in code's own labels ("Form 1040", "IT-201 line 20", "K-1 box 18")."""
    from abacus.modules.tax.fix_runner import FIX_LINES

    labels = [*BOX_LABELS.values(), *(ln.label for ln in FIX_LINES.values())]
    found: set[Decimal] = {Decimal(year)}
    for label in labels:
        found |= numbers_in(label)
    return frozenset(found)


def settle(
    answer: ExplainOutput | None, facts: Sequence[Fact], year: int
) -> tuple[str, tuple[UUID, ...]]:
    """Code's last word: verified citations only, sentences whose numbers are code's facts (or
    name a form, box, line or the year), and code's own sentence when nothing stands."""
    verified = {f.citation_id for f in facts}
    allowed: set[Decimal] = set(_structural(year))
    for f in facts:
        allowed |= numbers_in(f.value)
        amount = parse_amount(f.value)
        if amount is not None:
            allowed.add(amount)
    kept: list[str] = []
    cited: tuple[UUID, ...] = ()
    if answer is not None:
        for sentence in _SENTENCE.split(answer.text.strip()):
            if sentence and numbers_in(sentence) <= allowed:
                kept.append(sentence)
        cited = tuple(dict.fromkeys(c for c in answer.citation_ids if c in verified))
    if not kept or not cited:
        kept = [f"{f.label} reports {f.value}." for f in facts]
        cited = tuple(f.citation_id for f in facts)
    return " ".join(kept), cited


async def _judge(
    agent: AgentContext, facts: Sequence[Fact], entity: UUID, year: int
) -> ExplainOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.ai_gateway.context import DataSubject
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(ANALYST)
    context = (
        ContextBuilder()
        .task(
            {
                "facts": [
                    {"citation_id": str(f.citation_id), "label": f.label, "value": f.value}
                    for f in facts
                ]
            },
            untrusted=("facts",),  # box text read from a client's document
        )
        .subjects(DataSubject(entity, year))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=ExplainOutput,
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
    except Exception:  # a refused call: code's own sentence stands
        return None
    return cast(ExplainOutput, result.output)


@dataclass(frozen=True)
class ExplainResult:
    outcome: str  # explained · waiting_on_inputs · nothing_to_explain · refused
    needs: tuple[str, ...] = ()
    explanation_id: UUID | None = None
    citations: int = 0
    code: str | None = None


async def explain(agent: AgentContext, issue_id: UUID, entity: UUID, year: int) -> ExplainResult:
    from abacus.kernel.uow import uow
    from abacus.modules.agents.api import ToolCallIn, call_tool
    from abacus.modules.evidence.api import CitationAnchor, extracted_fields_of, record_citations
    from abacus.modules.review.api import record_explanation
    from abacus.modules.tax.form_line_citations import box_claim

    seq = 0

    async def tool(name: str, arguments: dict[str, object]):  # noqa: ANN202 -- ToolOutcome
        nonlocal seq
        seq += 1
        return await call_tool(
            agent,
            ToolCallIn(
                run_id=agent.agent_run_id, step_seq=seq, attempt=1, name=name, arguments=arguments
            ),
        )

    taxpayer: dict[str, object] = {"client_entity_id": str(entity), "tax_year": year}
    read = await tool("tax.read_return", taxpayer)
    if not read.ok:
        if read.code == "consent_required":
            return ExplainResult("waiting_on_inputs", needs=("consent_7216",), code=read.code)
        return ExplainResult("refused", code=read.code)
    docs = await tool("tax.list_documents", taxpayer)
    if not docs.ok:
        return ExplainResult("refused", code=docs.code)
    facts: list[Fact] = []
    for doc in cast(list[dict[str, object]], cast(dict[str, object], docs.result)["documents"]):
        version = UUID(str(doc["id"]))
        for f in await extracted_fields_of(agent.tenant, version):
            if f.field_key not in CITING_BOXES or not f.value_text:
                continue
            async with uow(agent.tenant) as tx:
                [recorded] = await record_citations(
                    tx,
                    actor=agent,
                    anchor=CitationAnchor(
                        type="issue",
                        id=issue_id,
                        ref=f.field_key,
                        engagement_id=agent.engagement_id,
                    ),
                    claims=[box_claim(version, f.page_no, f.bbox, f.value_text)],
                )
            if recorded.verified:
                facts.append(Fact(recorded.id, BOX_LABELS[f.field_key], f.value_text))
    if not facts:
        return ExplainResult("nothing_to_explain", code="no_verified_source")
    body, cited = settle(await _judge(agent, facts, entity, year), facts, year)
    explanation = await record_explanation(agent, issue_id, body, cited)
    return ExplainResult("explained", explanation_id=explanation, citations=len(cited))


# --- IssueExplainWorkflow ------------------------------------------------------------------------

_TIMEOUT: Final = timedelta(minutes=2)
_SHORT: Final = timedelta(seconds=30)
_RETRY: Final = RetryPolicy(maximum_attempts=3)


@dataclass(frozen=True)
class ExplainRunInput:
    tenant_id: str
    run_id: str
    issue_id: str
    client_entity_id: str
    tax_year: int


@dataclass(frozen=True)
class ExplainRunOutcome:
    outcome: str
    needs: list[str]
    explanation_id: str | None = None
    citations: int = 0
    code: str | None = None


def explain_workflow_id(tenant_id: str, run_id: str) -> str:
    return f"issue-explain:{tenant_id}:{run_id}"


@workflow.defn(name="IssueExplainWorkflow")
class IssueExplainWorkflow:
    """One activity; a missing consent ends the run `waiting_on_inputs` → failed (Explain is
    asked again by the person once the consent is recorded)."""

    async def _state(self, p: ExplainRunInput, state: str, reason: str | None) -> None:
        await workflow.execute_activity(
            "agents.run_v2.set_state",
            args=[p.tenant_id, p.run_id, state, reason, None],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, p: ExplainRunInput) -> str:
        await self._state(p, "running", None)
        outcome = await workflow.execute_activity(
            "tax.explain.explain",
            p,
            result_type=ExplainRunOutcome,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if outcome.outcome in ("refused", "waiting_on_inputs"):
            await self._state(p, "failed", outcome.code or outcome.outcome)
            return "failed"
        await self._state(p, "succeeded", None)
        return outcome.outcome


@activity.defn(name="tax.explain.explain")
async def explain_activity(p: ExplainRunInput) -> ExplainRunOutcome:
    from abacus.modules.agents.api import AgentRunNotRunning, load_run_v2_context

    try:
        agent = await load_run_v2_context(UUID(p.tenant_id), UUID(p.run_id))
    except AgentRunNotRunning:
        return ExplainRunOutcome("refused", [], code="run_ended")
    result = await explain(agent, UUID(p.issue_id), UUID(p.client_entity_id), p.tax_year)
    return ExplainRunOutcome(
        result.outcome,
        list(result.needs),
        str(result.explanation_id) if result.explanation_id else None,
        result.citations,
        result.code,
    )


WORKFLOWS: dict[type, WorkClass] = {IssueExplainWorkflow: "interactive"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (explain_activity,)


async def start_explain(ctx: AuthContext, issue_id: UUID) -> UUID:
    """The tax explainer (`review.api.register_explainer('tax_return', …)`)."""
    from abacus.modules.agents.api import open_capability_run
    from abacus.modules.tax.fix_runner import (
        _return_of_issue,  # pyright: ignore[reportPrivateUsage] -- the module's own
    )

    engagement, entity, year = await _return_of_issue(ctx, issue_id)
    run_id = await open_capability_run(
        ctx,
        agent_id=ANALYST,
        engagement_id=engagement,
        inputs={"issue_id": str(issue_id), "client_entity_id": str(entity), "tax_year": year},
        work_item_ref=f"issue:{issue_id}",
    )
    await dispatch(
        IssueExplainWorkflow,
        ExplainRunInput(str(ctx.tenant_id), str(run_id), str(issue_id), str(entity), year),
        id=explain_workflow_id(str(ctx.tenant_id), str(run_id)),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


__all__ = [
    "ACTIVITIES",
    "ANALYST",
    "WORKFLOWS",
    "ExplainOutput",
    "IssueExplainWorkflow",
    "explain",
    "explain_activity",
    "settle",
    "start_explain",
]
