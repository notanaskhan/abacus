"""`issues.fix_runner` for tax returns (T-04-T31; TASK-6819; DEC-3413; T-04 §6, AC-4.3, AC-4.4;
SHL-15 a', a''; ADR-005, ADR-050, ADR-052). PROTECTED (tax agents).

A person sets fix instructions on a return's issue (SHL-15 a, "Add 1,550 to line 2a and IT-201
line 20"); review seals them, moves the issue In progress and calls this runner, which opens the
person's run of `issues.fix_runner` and dispatches `FixRunWorkflow`. The run only ever proposes:

1. `tax.read_return` (C17, under C19's §7216 gate): no consent, the run waits on inputs.
2. The person's sealed instructions, read back for this issue's own run (`review.api`).
3. The model's judgment (`issues.fix_runner.tax@v1`, `FixJudgment`): which of code's fix lines
   the instructions name, add or set, and the amount as the person wrote it. Code holds the lines
   (`FIX_LINES`); a line it does not offer, or an amount that is not a number in the person's
   own instructions, is dropped (number provenance: the person's figure, never the model's).
4. `tax.read_worksheet` for each target's worksheet; code computes each new value (add: current +
   amount; set: amount).
5. A citation per row: a box on the return's own documents whose value is the amount (K-1 box 18A
   first), verified as the agent on the target field's anchor. An unverified or missing citation
   drops the row: no uncited row is ever proposed (DE-3).
6. One `tax.propose_field_changes` proposal ("ghost values" in SHL-15 a''), named to the issue
   (`review.api.record_fix_proposal`). The person approves it in SHL-10; that approval resolves
   the issue as them (`review.issue_runs`). The agent never resolves or edits a value.

`suggested_instruction` is code's suggested text for SHL-15 a (from the lines and the box), never
a model's; the screen renders it through AgentText as "Suggested by Accrued Agent".
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext, AuthContext

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes

FIX_RUNNER: Final = "issues.fix_runner"
PROMPT: Final = "issues.fix_runner.tax@v1"
RECORD_TYPE: Final = "tax_return"
Int = classified("internal")
Conf = classified("confidential")
_NUMBER: Final = re.compile(
    r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w,])|(?<![\w.,])\d+(?:\.\d+)?(?![\w,])"
)


@dataclass(frozen=True)
class FixLine:
    """A line a tax fix may change: its key, the words a person uses, and its worksheet field."""

    key: str
    label: str
    worksheet_key: str
    field_key: str


# Code's lines (the Feld 2025 return's worksheets, T-04-T28): Form 1040 line 2a is the Sch E p 2
# tax-exempt interest field; IT-201 line 20 is the IT-201 additions field.
FIX_LINES: Final[Mapping[str, FixLine]] = {
    "f1040.l2a": FixLine("f1040.l2a", "Form 1040 line 2a", "sch_e_p2", "tax_exempt_interest"),
    "it201.line20": FixLine("it201.line20", "IT-201 line 20", "it201", "line20"),
}
LineKey = Literal["f1040.l2a", "it201.line20"]
# The boxes that can cite a fix, most specific first (K-1 code A tax-exempt interest).
CITING_BOXES: Final = ("k1_1065.box18a", "k1_1065.box18", "k1_1120s.box16a", "k1_1120s.box16")


class FixChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    line: Annotated[LineKey, Int]
    op: Annotated[Literal["add", "set"], Int]
    # The amount exactly as the person wrote it ("1,550"); code parses and checks it.
    amount: Annotated[str, Field(min_length=1, max_length=20), Conf]


class FixJudgment(BaseModel):
    """`issues.fix_runner.tax@v1`'s answer: the lines the instructions name, nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    changes: Annotated[list[FixChange], Field(max_length=4), Int]


class FixInput(BaseModel):
    """The run's input: identifiers only; the instructions are read back sealed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: Annotated[UUID, Int]
    client_entity_id: Annotated[UUID, Int]
    tax_year: Annotated[int, Field(ge=2000, le=2100), Int]


def numbers_in(text_: str) -> frozenset[Decimal]:
    """Every number a person wrote ("1,550", "2a" is not one)."""
    found: set[Decimal] = set()
    for m in _NUMBER.finditer(text_):
        try:
            found.add(Decimal(m.group(0).replace(",", "")))
        except InvalidOperation:
            continue
    return frozenset(found)


def parse_amount(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


@dataclass(frozen=True)
class PlannedRow:
    line: FixLine
    op: Literal["add", "set"]
    amount: Decimal


def plan_rows(judgment: FixJudgment | None, instructions: str) -> tuple[PlannedRow, ...]:
    """Code's check of the model's reading: offered lines only, once each, and an amount that is
    one of the person's own numbers."""
    if judgment is None:
        return ()
    allowed = numbers_in(instructions)
    seen: set[str] = set()
    rows: list[PlannedRow] = []
    for change in judgment.changes:
        line = FIX_LINES.get(change.line)
        amount = parse_amount(change.amount)
        if line is None or amount is None or amount not in allowed or line.key in seen:
            continue
        seen.add(line.key)
        rows.append(PlannedRow(line, change.op, amount))
    return tuple(rows)


def new_value(row: PlannedRow, current: Decimal | None) -> Decimal:
    return row.amount if row.op == "set" else (current or Decimal(0)) + row.amount


def suggested_instruction(amount: Decimal, lines: Sequence[FixLine]) -> str:
    """SHL-15 a's suggested text (code's): "Add 1,550 to line 2a and IT-201 line 20"."""
    names = [ln.label.replace("Form 1040 ", "") for ln in lines]
    figure = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,}"
    return f"Add {figure} to {' and '.join(names)}"


@dataclass(frozen=True)
class FixResult:
    outcome: str  # proposed · waiting_on_inputs · nothing_to_propose · refused
    needs: tuple[str, ...] = ()
    proposal_id: UUID | None = None
    rows: int = 0
    code: str | None = None


# --- the run's steps (as the agent) --------------------------------------------------------------


async def _judge(
    agent: AgentContext, instructions: str, entity: UUID, year: int
) -> FixJudgment | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.ai_gateway.context import DataSubject
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(FIX_RUNNER)
    context = (
        ContextBuilder()
        .task(
            {
                "lines": [{"key": k, "label": v.label} for k, v in FIX_LINES.items()],
                "fix_instructions": instructions,
            },
            untrusted=("fix_instructions",),  # a person's words, still data (ADR-052)
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
                output_schema=FixJudgment,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant, agent.engagement_id, FIX_RUNNER, agent.agent_run_id
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
    except Exception:  # a refused call (consent, terms, budget): nothing is proposed
        return None
    return cast(FixJudgment, result.output)


async def _citing_box(
    agent: AgentContext, documents: Sequence[UUID], amount: Decimal
) -> tuple[UUID, int, tuple[float, float, float, float], str] | None:
    """A box on the return's documents whose value is the amount, the most specific first."""
    from abacus.modules.evidence.api import extracted_fields_of

    found: dict[str, tuple[UUID, int, tuple[float, float, float, float], str]] = {}
    for version in documents:
        for f in await extracted_fields_of(agent.tenant, version):
            if (
                f.field_key in CITING_BOXES
                and f.value_text
                and parse_amount(f.value_text) == amount
            ):
                found.setdefault(f.field_key, (version, f.page_no, f.bbox, f.value_text))
    for key in CITING_BOXES:
        if key in found:
            return found[key]
    return None


async def fix(agent: AgentContext, issue_id: UUID, entity: UUID, year: int) -> FixResult:
    """The run's steps (module docstring). The caller has the run in a v2 state."""
    from abacus.kernel.uow import uow
    from abacus.modules.agents.api import ToolCallIn, call_tool
    from abacus.modules.evidence.api import CitationAnchor, record_citations
    from abacus.modules.review.api import fix_instructions_of, record_fix_proposal
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
            return FixResult("waiting_on_inputs", needs=("consent_7216",), code=read.code)
        return FixResult("refused", code=read.code)
    instructions = await fix_instructions_of(agent, issue_id)
    if not instructions:
        return FixResult("nothing_to_propose", code="no_instructions")
    rows = plan_rows(await _judge(agent, instructions, entity, year), instructions)
    if not rows:
        return FixResult("nothing_to_propose", code="no_line_named")
    docs = await tool("tax.list_documents", taxpayer)
    if not docs.ok:
        return FixResult("refused", code=docs.code)
    documents = [
        UUID(str(d["id"]))
        for d in cast(list[dict[str, object]], cast(dict[str, object], docs.result)["documents"])
    ]
    changes: list[dict[str, object]] = []
    for row in rows:
        sheet = await tool(
            "tax.read_worksheet", {**taxpayer, "worksheet_key": row.line.worksheet_key}
        )
        if not sheet.ok:
            continue
        body = cast(dict[str, object], sheet.result)
        target = next(
            (
                f
                for f in cast(list[dict[str, object]], body["fields"])
                if f["field_key"] == row.line.field_key
            ),
            None,
        )
        box = await _citing_box(agent, documents, row.amount)
        if target is None or box is None:
            continue  # no field to change, or nothing on the return's documents says this amount
        current = parse_amount(str(target["value"])) if target.get("value") is not None else None
        async with uow(agent.tenant) as tx:
            [recorded] = await record_citations(
                tx,
                actor=agent,
                anchor=CitationAnchor(
                    type="field",
                    id=UUID(str(target["id"])),
                    ref=row.line.field_key,
                    engagement_id=agent.engagement_id,
                ),
                claims=[box_claim(box[0], box[1], box[2], box[3])],
            )
        if not recorded.verified:
            continue  # an uncited row is never proposed (DE-3)
        changes.append(
            {
                "worksheet_id": str(body["worksheet_id"]),
                "field_key": row.line.field_key,
                "after": str(new_value(row, current)),
                "citation_ids": [str(recorded.id)],
            }
        )
    if not changes:
        return FixResult("nothing_to_propose", code="uncited")
    proposed = await tool("tax.propose_field_changes", {**taxpayer, "changes": changes})
    if not proposed.ok:
        return FixResult("refused", code=proposed.code)
    proposal_id = UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    await record_fix_proposal(agent, issue_id, proposal_id)
    return FixResult("proposed", proposal_id=proposal_id, rows=len(changes))


# --- FixRunWorkflow (versioned, ADR-090) ---------------------------------------------------------

_TIMEOUT: Final = timedelta(minutes=3)
_SHORT: Final = timedelta(seconds=30)
_RETRY: Final = RetryPolicy(maximum_attempts=3)
MAX_WAITS: Final = 3


@dataclass(frozen=True)
class FixRunInput:
    tenant_id: str
    run_id: str
    issue_id: str
    client_entity_id: str
    tax_year: int


@dataclass(frozen=True)
class FixRunOutcome:
    outcome: str
    needs: list[str]
    proposal_id: str | None = None
    rows: int = 0
    code: str | None = None


def fix_workflow_id(tenant_id: str, run_id: str) -> str:
    return f"issue-fix:{tenant_id}:{run_id}"


@workflow.defn(name="FixRunWorkflow")
class FixRunWorkflow:
    """Orchestration only (identifiers in and out): the run running, the fix activity, a wait on
    a missing consent (the `inputs_ready` signal), then succeeded, or failed with its code."""

    def __init__(self) -> None:
        self._inputs = False
        self._stop = False

    @workflow.signal(name="inputs_ready")
    def inputs_ready(self) -> None:
        self._inputs = True

    @workflow.signal(name="stop")
    def stop(self) -> None:
        self._stop = True

    async def _state(
        self, p: FixRunInput, state: str, reason: str | None, blocked: dict[str, object] | None
    ) -> None:
        await workflow.execute_activity(
            "agents.run_v2.set_state",
            args=[p.tenant_id, p.run_id, state, reason, blocked],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, p: FixRunInput) -> str:
        await self._state(p, "running", None, None)
        for _ in range(MAX_WAITS + 1):
            outcome = await workflow.execute_activity(
                "tax.fix_runner.fix",
                p,
                result_type=FixRunOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            if outcome.outcome != "waiting_on_inputs":
                break
            await self._state(
                p, "waiting_on_inputs", "inputs", {"kind": "inputs", "needs": outcome.needs}
            )
            self._inputs = False
            await workflow.wait_condition(lambda: self._inputs or self._stop)
            if self._stop:
                await self._state(p, "cancelled", "stopped", None)
                return "cancelled"
            await self._state(p, "running", None, None)
        else:
            await self._state(p, "failed", "inputs_missing", None)
            return "failed"
        if outcome.outcome == "refused":
            await self._state(p, "failed", outcome.code or "refused", None)
            return "failed"
        await self._state(p, "succeeded", None, None)
        return outcome.outcome


@activity.defn(name="tax.fix_runner.fix")
async def fix_activity(p: FixRunInput) -> FixRunOutcome:
    from abacus.modules.agents.api import AgentRunNotRunning, load_run_v2_context

    try:
        agent = await load_run_v2_context(UUID(p.tenant_id), UUID(p.run_id))
    except AgentRunNotRunning:
        return FixRunOutcome("refused", [], code="run_ended")
    result = await _entity_fix(agent, UUID(p.issue_id))
    if result is None:
        result = await fix(agent, UUID(p.issue_id), UUID(p.client_entity_id), p.tax_year)
    return FixRunOutcome(
        result.outcome,
        list(result.needs),
        str(result.proposal_id) if result.proposal_id else None,
        result.rows,
        result.code,
    )


async def _entity_fix(agent: AgentContext, issue_id: UUID) -> FixResult | None:
    """T-05-T50 (DEC-4901): an issue on a return whose form has a workbook (an entity return) is
    fixed on its workbook's cells (`workbook_fix`); None for any other return."""
    from abacus.modules.review.api import issue_row
    from abacus.modules.tax import workbook_fix

    issue = await issue_row(agent.tenant, issue_id)
    if issue.record_type != RECORD_TYPE:
        return None
    form = await workbook_fix.workbook_form(agent.tenant, issue.record_id)
    if form is None:
        return None
    done = await workbook_fix.fix(agent, issue_id, issue.record_id, form)
    return FixResult(done.outcome, proposal_id=done.proposal_id, rows=done.rows, code=done.code)


WORKFLOWS: dict[type, WorkClass] = {FixRunWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (fix_activity,)


async def _return_of_issue(ctx: AuthContext, issue_id: UUID) -> tuple[UUID, UUID, int]:
    """(engagement, client entity, tax year) of the return the issue is on."""
    from abacus.kernel.db import tenant_session
    from abacus.kernel.errors import NotFound
    from abacus.modules.engagements.api import entity_of
    from abacus.modules.review.api import issue_row

    issue = await issue_row(ctx.tenant, issue_id)
    if issue.record_type != RECORD_TYPE:
        raise NotFound("tax_return")
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT engagement_id, tax_year FROM tax_returns WHERE work_item_id = :r"),
                {"r": issue.record_id},
            )
        ).first()
    if row is None:
        raise NotFound("tax_return")
    entity = await entity_of(ctx.tenant, row.engagement_id)
    if entity is None:
        raise NotFound("tax_return")
    return row.engagement_id, entity, int(row.tax_year)


async def start_fix(ctx: AuthContext, issue_id: UUID) -> UUID:
    """The tax fix runner (`review.api.register_fix_runner('tax_return', …)`): the person's run of
    `issues.fix_runner` (`agent_run.start`), then its workflow. Answers the run."""
    from abacus.modules.agents.api import open_capability_run

    engagement, entity, year = await _return_of_issue(ctx, issue_id)
    run_id = await open_capability_run(
        ctx,
        agent_id=FIX_RUNNER,
        engagement_id=engagement,
        inputs={"issue_id": str(issue_id), "client_entity_id": str(entity), "tax_year": year},
        work_item_ref=f"issue:{issue_id}",
    )
    await dispatch(
        FixRunWorkflow,
        FixRunInput(str(ctx.tenant_id), str(run_id), str(issue_id), str(entity), year),
        id=fix_workflow_id(str(ctx.tenant_id), str(run_id)),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


__all__ = [
    "ACTIVITIES",
    "FIX_LINES",
    "FIX_RUNNER",
    "WORKFLOWS",
    "FixJudgment",
    "FixRunWorkflow",
    "fix",
    "fix_activity",
    "numbers_in",
    "plan_rows",
    "start_fix",
    "suggested_instruction",
]
