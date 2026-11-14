"""A person's commands on a runtime-v2 run (P-10-T33; SPEC-647 §3.4, AC-W1, AC-W5, AC-W6, AC-W10;
C6 v2 `docs/contracts/agent-runs.md` §9). PROTECTED (agents).

PLAN-001: a plan decision is written here and nowhere else. Every command is a person's own act:

1. the route's matrix action on the run's engagement (`runs._run`: walls first, 404; `agent: deny`
   and `system: deny`, 403);
2. `require_live_human` here (never an agent, the platform, a client or a support session);
3. the database: `agent_plans_decision_is_human` and `run_sign_offs_human` bind the row to the
   session's actor, so an agent or system context is refused even past the first two.

Then the row is written (one audit event per command, in the same unit of work) and the run's
workflow is woken (`plan_decided`, `question_answered`, `redirected`, `step_retry`, `stop`). The
workflow reads the rows itself; a lost signal is caught up by the next one (DEC-3180).

- **Plan**: approve, edit and cancel each insert a new `agent_plans` version (insert-only) against
  `expected_version` (409 `plan_version_conflict`); never optimistic. An edit keeps, drops and
  reorders the newest version's step keys (the dock's "Change order…"); a kept step that depends
  on a dropped one is refused. An approval on a run past its plan approval is a redirect (AC-W10).
- **Questions**: the run's open question, answered with one of its options (or free text where
  `other_allowed`), or skipped (its skip default is the workflow's to apply, AC-W5).
- **Redirect** (`messages`): the person's note joins the run's items as a fingerprint, never its
  text (run events stream as stored); the workflow re-reads the newest approved plan.
- **Retry** one failed step; **stop** the run.
- **Sign-off** of an ended run: every open issue (a failed step) and open decision (a held card)
  must be acknowledged by id (409 `sign_off_unacknowledged`); one row per run.
- **Feedback**: a thumb and a reason code on a step of a run the person may read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import signal_workflow
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.agents.events import RunPlanDecided
from abacus.modules.agents.run_commands import RetryScope, RunNotEnded, retry_step, wake
from abacus.modules.agents.file_tools import FOLDER_LABELS
from abacus.modules.agents.run_activities import plan_rules
from abacus.modules.agents.run_plan import READ_SOURCES, PlanStep, validate_plan
from abacus.modules.agents.run_views import TERMINAL
from abacus.modules.agents.run_waits import run_workflow_id
from abacus.modules.agents.runs import (
    RunView,
    _run,  # pyright: ignore[reportPrivateUsage] -- same module
    run_view,
)
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of

_AWAITING: Final = "awaiting_plan_approval"
_ENDED: Final = frozenset({"succeeded", "approved", "partially_approved", "rejected", "failed"})
_DECIDABLE: Final = frozenset({"proposed", "edited"})
# The audited action of each decision (literals, so the catalogue check sees them).
_PLAN_ACTION: Final = {
    "approved": "agent_run.plan_approved",
    "edited": "agent_run.plan_edited",
    "cancelled": "agent_run.plan_cancelled",
}
_QUESTION_ACTION: Final = {
    "answered": "agent_run.question_answered",
    "skipped": "agent_run.question_skipped",
}


class PlanVersionConflict(DomainConflict):
    """`expected_version` is not the plan's newest version: someone decided first."""

    code = "plan_version_conflict"


class PlanNotDecidable(DomainConflict):
    code = "plan_not_decidable"


class PlanEditInvalid(DomainInvalid):
    code = "plan_edit_invalid"


class QuestionNotOpen(DomainConflict):
    code = "question_not_open"


class AnswerInvalid(DomainInvalid):
    code = "answer_invalid"


class RunEnded(DomainConflict):
    code = "run_ended"


class SignOffUnacknowledged(DomainConflict):
    """An open issue or decision on the run is not in the sign-off's acknowledgements."""

    code = "sign_off_unacknowledged"


class RunAlreadySignedOff(DomainConflict):
    code = "run_already_signed_off"


def require_live_human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform, a client or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RunHead:
    id: UUID
    # None for a firm-level run (W-02-T21: a Workbench firm session's plan run).
    engagement_id: UUID | None
    state: str | None
    plan_id: UUID | None
    signed_off_by: UUID | None


async def _head(ctx: AuthContext, run_id: UUID, action: str) -> RunHead:
    """The run, authorised `action` on its engagement (404 walled or unknown), and a person.
    W-02-T21 (DEC-4943): a firm-level run (no engagement) is its initiator's alone: anyone else
    reads 404, and the initiator needs the action at firm level."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT r.state, r.plan_id, r.engagement_id, r.initiator_user_id, r.shadow, "
                    "s.signed_by AS signed_off_by FROM agent_runs r "
                    "LEFT JOIN run_sign_offs s ON s.run_id = r.id WHERE r.id = :run"
                ),
                {"run": run_id},
            )
        ).first()
    if row is None or row.shadow:
        raise NotFound("agent_run")
    if row.engagement_id is None:
        if row.initiator_user_id != ctx.user_id:
            raise NotFound("agent_run")
        await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    else:
        await _run(ctx, run_id, action)
    require_live_human(ctx, action)
    return RunHead(run_id, row.engagement_id, row.state, row.plan_id, row.signed_off_by)


# --- plan --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanRead:
    """WB-03a "Data it will read": one source, its words (code's) and its count."""

    source: str
    label: str
    count: int


@dataclass(frozen=True)
class PlanWrite:
    """WB-03a "Writes that need your approval": the step, its action and who approves it."""

    step_key: str
    action: str
    label: str
    approver_name: str | None


@dataclass(frozen=True)
class PlanView:
    id: UUID
    run_id: UUID
    version: int
    state: str
    steps: list[PlanStep]
    sources: list[str]
    decided_by: str | None
    decided_at: datetime | None
    # W-02-T19: the plan card's fields, derived by code from the version's steps.
    reads: list[PlanRead] = field(default_factory=list[PlanRead])
    writes: list[PlanWrite] = field(default_factory=list[PlanWrite])


# The run's row is locked, not the plan's: `agent_plans` is insert-only (no UPDATE grant, so no
# FOR UPDATE), and `(run_id, version)` is unique, so two deciders of one version cannot both land.
_LOCK_RUN: Final = text("SELECT id FROM agent_runs WHERE id = :run FOR UPDATE")
_LATEST_PLAN: Final = text(
    "SELECT id, version, state, steps, sources, decided_by, decided_at FROM agent_plans "
    "WHERE run_id = :run ORDER BY version DESC LIMIT 1"
)


async def _decide(
    ctx: AuthContext,
    run_id: UUID,
    expected_version: int,
    state: str,
    steps: Sequence[str] | None = None,
    labels: Mapping[str, str] | None = None,
) -> PlanView:
    head = await _head(ctx, run_id, "agent_run.approve_plan")
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_LOCK_RUN, {"run": run_id})
        latest = (await tx.session.execute(_LATEST_PLAN, {"run": run_id})).first()
        if latest is None:
            raise NotFound("agent_plan")
        if int(latest.version) != expected_version:
            raise PlanVersionConflict(facts={"version": int(latest.version)})
        current = [PlanStep.parse(s) for s in cast(list[dict[str, object]], latest.steps or [])]
        if state == "edited":
            if latest.state == "cancelled":  # a cancelled plan is not edited back to life
                raise PlanNotDecidable(facts={"state": "cancelled"})
            current = _edited(current, steps or (), labels or {})
            # W-02-T19 (AC-P3): an edited plan is validated again before it may be approved:
            # its writes declared, no reserved action, each approver still holding the write.
            problems = validate_plan(
                current,
                await plan_rules(str(ctx.tenant_id), str(run_id), [s.dump() for s in current]),
            )
            if problems:
                raise PlanEditInvalid(facts={"reason": "plan_invalid", "problems": problems})
        elif (state == "approved" and latest.state not in _DECIDABLE) or (
            state == "cancelled" and (latest.state not in _DECIDABLE or head.state != _AWAITING)
        ):
            raise PlanNotDecidable(facts={"state": str(latest.state)})
        if head.state in TERMINAL:
            raise RunEnded(facts={"state": str(head.state)})
        version = int(latest.version) + 1
        plan_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO agent_plans (tenant_id, run_id, version, steps, sources, state, "
                    "decided_by, decided_at) VALUES (:t, :run, :v, CAST(:steps AS jsonb), "
                    "CAST(:sources AS jsonb), :state, :by, clock_timestamp()) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "run": run_id,
                    "v": version,
                    "steps": json.dumps([s.dump() for s in current]),
                    "sources": json.dumps(latest.sources or []),
                    "state": state,
                    "by": ctx.user_id,
                },
            ),
        )
        await tx.session.execute(
            text("UPDATE agent_runs SET plan_id = :plan WHERE id = :run"),
            {"plan": plan_id, "run": run_id},
        )
        tx.record(
            _PLAN_ACTION[state],
            target=Target("agent_run", run_id),
            after=Ref(version=version, steps=len(current)),
        )
        # P-10-T49 (C13): the plan's "Waiting on you" row closes on the decision itself, not on
        # the workflow's later state change.
        tx.emit(
            RunPlanDecided(
                run_id=run_id, engagement_id=head.engagement_id, state=state, version=version
            )
        )
    workflow = run_workflow_id(str(ctx.tenant_id), str(run_id))
    if head.state == _AWAITING:
        await signal_workflow(workflow, "plan_decided", state)
    elif state == "approved":
        await signal_workflow(workflow, "redirected")
    return await plan_view(ctx, run_id)


def _edited(
    current: list[PlanStep], keys: Sequence[str], labels: Mapping[str, str]
) -> list[PlanStep]:
    """The newest version's steps, kept and reordered by key; nothing new is added. W-02-T19
    (WB-03a2, steps become fields): a kept step's label may be reworded; what it does (tool,
    arguments, writes, approver) is not editable here."""
    by_key = {s.key: s for s in current}
    if len(set(keys)) != len(keys) or any(k not in by_key for k in keys):
        raise PlanEditInvalid(facts={"reason": "unknown_or_repeated_key"})
    if any(k not in keys for k in labels):
        raise PlanEditInvalid(facts={"reason": "label_for_dropped_step"})
    kept = set(keys)
    for key in keys:
        if any(d not in kept for d in by_key[key].depends_on):
            raise PlanEditInvalid(facts={"reason": "depends_on_dropped"})
    return [
        replace(by_key[k], label=labels[k].strip()) if labels.get(k, "").strip() else by_key[k]
        for k in keys
    ]


async def approve_plan(ctx: AuthContext, run_id: UUID, expected_version: int) -> PlanView:
    return await _decide(ctx, run_id, expected_version, "approved")


async def edit_plan(
    ctx: AuthContext,
    run_id: UUID,
    expected_version: int,
    steps: Sequence[str],
    labels: Mapping[str, str] | None = None,
) -> PlanView:
    return await _decide(ctx, run_id, expected_version, "edited", steps, labels)


async def cancel_plan(ctx: AuthContext, run_id: UUID, expected_version: int) -> PlanView:
    return await _decide(ctx, run_id, expected_version, "cancelled")


async def read_plan(ctx: AuthContext, run_id: UUID) -> PlanView:
    """W-02-T21: the run's newest plan version for its reader (`agent_run.read`, as `_head`)."""
    await _head(ctx, run_id, "agent_run.read")
    return await plan_view(ctx, run_id)


async def plan_view(ctx: AuthContext, run_id: UUID) -> PlanView:
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, version, state, steps, sources, decided_by, decided_at "
                    "FROM agent_plans WHERE run_id = :run ORDER BY version DESC LIMIT 1"
                ),
                {"run": run_id},
            )
        ).first()
    if row is None:
        raise NotFound("agent_plan")
    steps = [PlanStep.parse(s) for s in cast(list[dict[str, object]], row.steps or [])]
    approvers = {UUID(s.approver_user_id) for s in steps if s.writes and s.approver_user_id}
    names = await names_of([u for u in [row.decided_by, *approvers] if u is not None])
    return PlanView(
        row.id,
        run_id,
        int(row.version),
        str(row.state),
        steps,
        [str(s) for s in cast(list[object], row.sources or [])],
        names.get(row.decided_by) if row.decided_by else None,
        row.decided_at,
        plan_reads(steps),
        [
            PlanWrite(
                s.key,
                write,
                write_label(s, steps),
                names.get(UUID(s.approver_user_id)) if s.approver_user_id else None,
            )
            for s in steps
            for write in s.writes
        ],
    )


def plan_reads(steps: Sequence[PlanStep]) -> list[PlanRead]:
    """W-02-T19 (WB-03a): each declared source once, in first-read order, at its largest count."""
    found: dict[str, int] = {}
    for step in steps:
        for source, count in step.reads:
            if source in READ_SOURCES and count >= 0:
                found[source] = max(found.get(source, 0), count)
    return [PlanRead(s, READ_SOURCES[s], n) for s, n in found.items()]


def write_label(step: PlanStep, steps: Sequence[PlanStep]) -> str:
    """A write's words, rendered by code from what the step will do: a file save names the
    workbook its build step makes and the folder it goes to (WB-03a "Create file … in Files ›
    …"); anything else is the step's label."""
    if step.tool == "files.propose_save":
        folder = FOLDER_LABELS.get(str(step.arguments.get("folder") or "deliverables"))
        build = next(
            (
                s
                for s in steps
                if s.key in step.depends_on and s.tool == "files.build_workbook"
            ),
            None,
        )
        name = build.arguments.get("name") if build is not None else None
        if folder is not None and isinstance(name, str) and name:
            return f"Create file {name}.xlsx in Files \u203a {folder}"
    return step.label


# --- questions ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionView:
    id: UUID
    run_id: UUID
    step_id: UUID | None
    state: str
    prompt: str
    options: list[tuple[str, str]]
    allow_free_text: bool
    answered_by: str | None
    answered_at: datetime | None


def _options(steps: object) -> list[tuple[str, str]]:
    first = cast(list[dict[str, object]], steps or [{}])[0] if steps else {}
    found: list[tuple[str, str]] = []
    for option in cast(list[object], first.get("options") or []):
        if isinstance(option, dict):
            raw = cast(dict[str, object], option)
            key = str(raw.get("key", ""))
            found.append((key, str(raw.get("label") or key)))
        else:
            found.append((str(option), str(option)))
    return [o for o in found if o[0]]


def _prompt(steps: object) -> str:
    first = cast(list[dict[str, object]], steps or [{}])[0] if steps else {}
    return str(first.get("prompt") or first.get("label") or first.get("key") or "")


async def _question(session: AsyncSession, run_id: UUID, question_id: UUID) -> QuestionView:
    row = (
        await session.execute(
            text(
                "SELECT id, step_id, state, steps, other_allowed, answered_by, answered_at "
                "FROM agent_questions WHERE id = :q AND run_id = :run"
            ),
            {"q": question_id, "run": run_id},
        )
    ).first()
    if row is None:
        raise NotFound("agent_question")
    names = await names_of([row.answered_by]) if row.answered_by else {}
    return QuestionView(
        row.id,
        run_id,
        row.step_id,
        str(row.state),
        _prompt(row.steps),
        _options(row.steps),
        bool(row.other_allowed),
        names.get(row.answered_by) if row.answered_by else None,
        row.answered_at,
    )


async def _settle_question(
    ctx: AuthContext, run_id: UUID, question_id: UUID, state: str, answer: dict[str, str] | None
) -> QuestionView:
    await _head(ctx, run_id, "agent_run.answer")
    async with uow(ctx.tenant) as tx:
        current = await _question(tx.session, run_id, question_id)
        if current.state != "open":
            raise QuestionNotOpen(facts={"state": current.state})
        if answer is not None:
            option = answer.get("option")
            if option is not None and option not in {k for k, _ in current.options}:
                raise AnswerInvalid(facts={"reason": "unknown_option"})
            if "text" in answer and not current.allow_free_text:
                raise AnswerInvalid(facts={"reason": "free_text_not_allowed"})
        settled = await tx.session.scalar(
            text(
                "UPDATE agent_questions SET state = :state, answer = CAST(:answer AS jsonb), "
                "answered_by = :by, answered_at = clock_timestamp() "
                "WHERE id = :q AND run_id = :run AND state = 'open' RETURNING id"
            ),
            {
                "state": state,
                "answer": json.dumps(answer) if answer is not None else None,
                "by": ctx.user_id,
                "q": question_id,
                "run": run_id,
            },
        )
        if settled is None:
            raise QuestionNotOpen(facts={"state": "decided"})
        fingerprint = _sha(answer["text"]) if answer and "text" in answer else None
        tx.record(
            _QUESTION_ACTION[state],
            target=Target("agent_run", run_id),
            after=Ref(question=question_id, answer=fingerprint)
            if fingerprint
            else Ref(question=question_id),
        )
    await wake(ctx.tenant_id, run_id, "question_answered")
    async with tenant_session(ctx.tenant) as session:
        return await _question(session, run_id, question_id)


async def answer_question(
    ctx: AuthContext,
    run_id: UUID,
    question_id: UUID,
    *,
    option_key: str | None,
    free_text: str | None,
) -> QuestionView:
    if (option_key is None) == (free_text is None or not free_text.strip()):
        raise AnswerInvalid(facts={"reason": "one_of_option_or_text"})
    answer = {"option": option_key} if option_key is not None else {"text": str(free_text).strip()}
    return await _settle_question(ctx, run_id, question_id, "answered", answer)


async def skip_question(ctx: AuthContext, run_id: UUID, question_id: UUID) -> QuestionView:
    return await _settle_question(ctx, run_id, question_id, "skipped", None)


# --- control -----------------------------------------------------------------------------------


async def _live(ctx: AuthContext, run_id: UUID) -> RunHead:
    head = await _head(ctx, run_id, "agent_run.control")
    if head.state is None or head.state in TERMINAL:
        raise RunEnded(facts={"state": str(head.state)})
    return head


async def _append_item(
    tx: UnitOfWork, tenant_id: UUID, run_id: UUID, payload: dict[str, object]
) -> int:
    seq = cast(
        int,
        await tx.session.scalar(
            text(
                "UPDATE agent_runs SET event_seq = event_seq + 1 WHERE id = :run "
                "RETURNING event_seq"
            ),
            {"run": run_id},
        ),
    )
    await tx.session.execute(
        text(
            "INSERT INTO run_events (tenant_id, run_id, run_seq, type, payload) "
            "VALUES (:t, :run, :seq, 'item.appended', CAST(:payload AS jsonb))"
        ),
        {"t": tenant_id, "run": run_id, "seq": seq, "payload": json.dumps(payload)},
    )
    return seq


async def redirect(ctx: AuthContext, run_id: UUID, body: str) -> None:
    """The person's note joins the items as a fingerprint (the stream sends payloads as stored,
    so the text never travels in it); the workflow re-reads the newest approved plan."""
    await _live(ctx, run_id)
    note = body.strip()
    if not note:
        raise AnswerInvalid(facts={"reason": "empty_message"})
    async with uow(ctx.tenant) as tx:
        seq = await _append_item(
            tx,
            ctx.tenant_id,
            run_id,
            {
                "kind": "user",
                "code": "redirect",
                "actor_user_id": str(ctx.user_id),
                "ref_type": "run_message",
                "body_sha256": _sha(note),
            },
        )
        tx.record(
            "agent_run.redirected",
            target=Target("agent_run", run_id),
            after=Ref(seq=seq, body=_sha(note)),
        )
    await wake(ctx.tenant_id, run_id, "redirected")


async def retry(
    ctx: AuthContext, run_id: UUID, step_id: UUID, scope: RetryScope = "all"
) -> str:
    await _live(ctx, run_id)
    async with tenant_session(ctx.tenant) as session:
        seq = await session.scalar(
            text("SELECT seq FROM agent_run_steps WHERE id = :step AND run_id = :run"),
            {"step": step_id, "run": run_id},
        )
    if seq is None:
        raise NotFound("agent_run_step")
    return await retry_step(ctx, run_id, int(seq), scope)


async def stop(ctx: AuthContext, run_id: UUID) -> None:
    await _live(ctx, run_id)
    async with uow(ctx.tenant) as tx:
        tx.record("agent_run.stop_requested", target=Target("agent_run", run_id), after=Ref())
    await wake(ctx.tenant_id, run_id, "stop")


# --- sign-off ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenItems:
    issues: frozenset[UUID]  # failed steps (their latest row per plan step)
    decisions: frozenset[UUID]  # held decision cards not yet decided


async def open_items(session: AsyncSession, run_id: UUID) -> OpenItems:
    rows = (
        await session.execute(
            text(
                "SELECT DISTINCT ON (coalesce(plan_step_key, id::text)) id, state, kind, needs "
                "FROM agent_run_steps WHERE run_id = :run "
                "ORDER BY coalesce(plan_step_key, id::text), seq DESC"
            ),
            {"run": run_id},
        )
    ).all()
    issues = frozenset(r.id for r in rows if r.state == "failed")
    decisions: set[UUID] = set()
    for r in rows:
        card = cast(dict[str, object], r.needs or {}).get("card_id")
        if r.state == "blocked" and card is not None:
            decisions.add(UUID(str(card)))
    return OpenItems(issues, frozenset(decisions))


async def sign_off(
    ctx: AuthContext,
    run_id: UUID,
    *,
    issues: Sequence[UUID],
    decisions: Sequence[UUID],
) -> None:
    head = await _head(ctx, run_id, "agent_run.sign_off")
    if head.state not in _ENDED:
        raise RunNotEnded(facts={"state": str(head.state)})
    if head.signed_off_by is not None:
        raise RunAlreadySignedOff
    async with uow(ctx.tenant) as tx:
        found = await open_items(tx.session, run_id)
        missing_issues = found.issues - set(issues)
        missing_decisions = found.decisions - set(decisions)
        if missing_issues or missing_decisions:
            raise SignOffUnacknowledged(
                facts={"issues": len(missing_issues), "decisions": len(missing_decisions)}
            )
        acked_issues = sorted(str(i) for i in found.issues)
        acked_decisions = sorted(str(d) for d in found.decisions)
        signed = await tx.session.scalar(
            text(
                "INSERT INTO run_sign_offs (tenant_id, run_id, signed_by, open_issues_ack, "
                "decisions_ack) VALUES (:t, :run, :by, CAST(:issues AS jsonb), "
                "CAST(:decisions AS jsonb)) ON CONFLICT (tenant_id, run_id) DO NOTHING "
                "RETURNING signed_at"
            ),
            {
                "t": ctx.tenant_id,
                "run": run_id,
                "by": ctx.user_id,
                "issues": json.dumps(acked_issues),
                "decisions": json.dumps(acked_decisions),
            },
        )
        if signed is None:
            raise RunAlreadySignedOff
        # The sign-off is its insert-only row (one per run): a finished run's own row is
        # forward-only (`agent_runs_forward_only`), so the run is not written again.
        tx.record(
            "agent_run.signed_off",
            target=Target("agent_run", run_id),
            after=Ref(issues=len(acked_issues), decisions=len(acked_decisions)),
        )


# --- feedback ----------------------------------------------------------------------------------


async def create_feedback(
    ctx: AuthContext,
    *,
    run_id: UUID,
    step_id: UUID | None,
    rating: str,
    reason: str | None,
) -> UUID:
    """A thumb on a step of a run the person may read (on the run's first step when none is
    named); one per person and target, the first one kept (insert-only)."""
    await _run(ctx, run_id, "agent_feedback.create")
    require_live_human(ctx, "agent_feedback.create")
    async with uow(ctx.tenant) as tx:
        target = await tx.session.scalar(
            text(
                "SELECT id FROM agent_run_steps WHERE run_id = :run "
                "AND (CAST(:step AS uuid) IS NULL OR id = :step) ORDER BY seq LIMIT 1"
            ),
            {"run": run_id, "step": step_id},
        )
        if target is None:
            raise NotFound("agent_run_step")
        feedback = await tx.session.scalar(
            text(
                "INSERT INTO agent_feedback (tenant_id, target_kind, target_id, rating, "
                "reason_code, created_by) VALUES (:t, 'step', :target, :rating, :reason, :by) "
                "ON CONFLICT (tenant_id, target_kind, target_id, created_by) DO NOTHING "
                "RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "target": target,
                "rating": rating,
                "reason": reason,
                "by": ctx.user_id,
            },
        )
        if feedback is None:
            feedback = await tx.session.scalar(
                text(
                    "SELECT id FROM agent_feedback WHERE target_kind = 'step' "
                    "AND target_id = :target AND created_by = :by"
                ),
                {"target": target, "by": ctx.user_id},
            )
            return cast(UUID, feedback)
        tx.record(
            "agent_feedback.created",
            target=Target("agent_run", run_id),
            after=Ref(step=cast(UUID, target), up=int(rating == "up")),
        )
    return cast(UUID, feedback)


# --- the run, after a command ------------------------------------------------------------------


@dataclass(frozen=True)
class RunState:
    """What `RunV2Out` reads beside `runs.run_view`: the v2 columns a command moves."""

    view: RunView
    mode: str
    plan_id: UUID | None
    parent_run_id: UUID | None
    subject_ref: str | None
    auto_mode: bool
    region: str | None
    session_id: UUID | None
    started_at: datetime | None
    signed_off_by: str | None
    signed_off_at: datetime | None
    version: int
    actions: list[str]


def run_actions(state: str | None, allowed: Sequence[str], signed: bool) -> list[str]:
    """C6 v2's `allowed_actions`: the caller's matrix actions, narrowed by the run's state."""
    held = set(allowed)
    out: list[str] = []
    if "agent_run.approve_plan" in held and state == _AWAITING:
        out += ["approve_plan", "edit_plan", "cancel_plan"]
    if "agent_run.answer" in held and state in ("needs_input", "waiting_on_inputs"):
        out += ["answer", "skip"]
    if "agent_run.control" in held and state is not None and state not in TERMINAL:
        out += ["redirect", "retry", "stop"]
    if "agent_run.sign_off" in held and state in _ENDED and not signed:
        out.append("sign_off")
    return out


async def run_state(ctx: AuthContext, run_id: UUID) -> RunState:
    view = await run_view(ctx, run_id)
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT r.mode, r.plan_id, r.parent_run_id, r.subject_ref, r.auto_mode, "
                    "r.region, r.session_id, r.started_at, s.signed_by AS signed_off_by, "
                    "s.signed_at AS signed_off_at, r.event_seq, r.state "
                    "FROM agent_runs r LEFT JOIN run_sign_offs s ON s.run_id = r.id "
                    "WHERE r.id = :run"
                ),
                {"run": run_id},
            )
        ).first()
    if row is None:
        raise NotFound("agent_run")
    names = await names_of([row.signed_off_by]) if row.signed_off_by else {}
    return RunState(
        view,
        str(row.mode or "run"),
        row.plan_id,
        row.parent_run_id,
        row.subject_ref,
        bool(row.auto_mode),
        row.region,
        row.session_id,
        row.started_at,
        names.get(row.signed_off_by) if row.signed_off_by else None,
        row.signed_off_at,
        int(row.event_seq or 0),
        run_actions(row.state, view.allowed_actions, row.signed_off_by is not None),
    )


__all__ = [
    "AnswerInvalid",
    "OpenItems",
    "PlanEditInvalid",
    "PlanNotDecidable",
    "PlanVersionConflict",
    "PlanView",
    "QuestionNotOpen",
    "QuestionView",
    "RunAlreadySignedOff",
    "RunEnded",
    "RunState",
    "SignOffUnacknowledged",
    "answer_question",
    "approve_plan",
    "cancel_plan",
    "create_feedback",
    "edit_plan",
    "open_items",
    "plan_view",
    "read_plan",
    "redirect",
    "require_live_human",
    "retry",
    "run_actions",
    "run_state",
    "sign_off",
    "skip_question",
    "stop",
]
