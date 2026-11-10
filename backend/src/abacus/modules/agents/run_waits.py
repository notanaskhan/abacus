"""AgentRunWorkflow part 2's waits (P-10-T32; SPEC-647 §3.4 AC-W4, AC-W5, AC-W6; ADR-005, ADR-090).
PROTECTED (agents).

A step that needs a person holds only its own branch:

- **Question** (`kind = question` or `approval`): one `agent_questions` row (the run's one open
  question, its options and skip default as the plan step carries them), the step
  `waiting_on_inputs`, the run `needs_input`. P-10-T33's route writes the answer or the skip
  (`require_live_human`) and signals `question_answered`; the workflow then reads the row. A skip
  applies the step's skip default and records it (`skip_default_applied`, AC-W5); a skip with no
  default leaves the step `skipped`, so only its dependants stop.
- **Decision** (`kind = decision`): a C3 decision card raised through `review.api` in the agent's
  task scope (the reserved person named by the step), the step `blocked`, the run
  `blocked_on_decision`. `decision.decided` (the reserved person's row, actor kind human) is the
  only way on: the consumer below signals the run, and only the held branch resumes (AC-W4).
- **Retry** (AC-W6): a failed step's retry is a new `agent_run_steps` row with `retry_of_step_id`,
  so the trace shows both.

Activities return identifiers and codes only; no question text or answer enters the history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import signal_workflow
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.agents.service import AgentRunNotRunning, load_run_v2_context
from abacus.modules.review.api import card_decision, raise_decision_card

_READER: Final = "agent-run-v2"
_log = get_logger(__name__)
QUESTION_KINDS: Final = frozenset({"question", "approval"})
DECISION_SIGNAL: Final = "decision_decided"


def _tenant(tenant_id: str, run_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", f"{_READER}:{run_id}")


def run_workflow_id(tenant_id: str, run_id: str) -> str:
    return f"agent_run:{tenant_id}:{run_id}"


@dataclass(frozen=True)
class WaitOpened:
    state: str  # waiting_on_inputs · blocked · failed
    ref: str | None = None  # the question's or the card's id
    error_code: str | None = None


async def open_wait(
    tenant_id: str, run_id: str, step_id: UUID, step: dict[str, object]
) -> WaitOpened:
    """The step's question or decision card, written beside its row (`execute_step` calls this
    for the three kinds that wait on a person)."""
    kind = str(step.get("kind"))
    arguments = cast(dict[str, object], step.get("arguments") or {})
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    if kind in QUESTION_KINDS:
        single: list[dict[str, object]] = [
            {"key": str(step.get("key", "")), "options": arguments.get("options") or []}
        ]
        questions: object = arguments.get("questions") or single
        recommended = arguments.get("recommended")
        async with uow(tenant) as tx:
            question = cast(
                UUID | None,
                await tx.session.scalar(
                    text(
                        "INSERT INTO agent_questions (tenant_id, run_id, step_id, steps, "
                        "recommended, other_allowed) VALUES (:t, :run, :step, "
                        "CAST(:steps AS jsonb), :rec, :other) ON CONFLICT DO NOTHING RETURNING id"
                    ),
                    {
                        "t": UUID(tenant_id),
                        "run": run,
                        "step": step_id,
                        "steps": json.dumps(questions, sort_keys=True, default=str),
                        "rec": str(recommended)[:80] if recommended is not None else None,
                        "other": bool(arguments.get("other_allowed", False)),
                    },
                ),
            )
            if question is None:
                # The run's one open question is another step's: this one fails, its branch alone.
                return WaitOpened("failed", error_code="question_already_open")
            default = arguments.get("skip_default")
            await _hold(
                tx,
                step_id,
                "waiting_on_inputs",
                {
                    "question_id": str(question),
                    "skip_default": str(default) if default is not None else None,
                },
            )
            tx.record(
                "agent_run.question_opened",
                target=Target("agent_run", run),
                after=Ref(question=question, step=step_id),
            )
        return WaitOpened("waiting_on_inputs", str(question))
    # A decision card, raised as the agent within its task scope (`decision_card.raise`).
    try:
        agent = await load_run_v2_context(UUID(tenant_id), run)
    except AgentRunNotRunning:
        return WaitOpened("failed", error_code="run_ended")
    if agent.engagement_id is None:
        return WaitOpened("failed", error_code="decision_needs_engagement")
    reserved = arguments.get("reserved_user_id")
    recommended = arguments.get("recommended_option_key")
    work_item = arguments.get("work_item_id")
    card = await raise_decision_card(
        agent,
        engagement_id=agent.engagement_id,
        kind=str(arguments.get("decision_kind", "")),
        question_key=str(arguments.get("question_key", step.get("key", ""))),
        work_item_id=UUID(str(work_item)) if work_item else None,
        reserved_user_id=UUID(str(reserved)) if reserved else None,
        recommended_option_key=str(recommended) if recommended else None,
    )
    async with uow(tenant) as tx:
        await _hold(tx, step_id, "blocked", {"card_id": str(card)})
        tx.record(
            "agent_run.decision_raised",
            target=Target("agent_run", run),
            after=Ref(card=card, step=step_id),
        )
    return WaitOpened("blocked", str(card))


async def _hold(tx: UnitOfWork, step_id: UUID, state: str, needs: dict[str, str | None]) -> None:
    await tx.session.execute(
        text(
            "UPDATE agent_run_steps SET state = :state, needs = CAST(:needs AS jsonb) "
            "WHERE id = :id"
        ),
        {"state": state, "needs": json.dumps(needs, sort_keys=True), "id": step_id},
    )


@dataclass(frozen=True)
class WaitState:
    """`open` while a person has not acted; else the step's new state and how it got there."""

    resolution: str  # open · answered · skipped · skipped_default · decided · expired
    step_state: str | None = None  # succeeded · skipped (None while open)


_QUESTION: Final = text(
    "SELECT q.id, q.state, q.answer, q.skip_default_applied, s.id AS step_id, s.needs "
    "FROM agent_run_steps s LEFT JOIN agent_questions q ON q.id = "
    "CAST(s.needs ->> 'question_id' AS uuid) WHERE s.run_id = :run AND s.seq = :seq"
)
_CARD: Final = text(
    "SELECT s.id AS step_id, s.needs, s.state FROM agent_run_steps s "
    "WHERE s.run_id = :run AND s.seq = :seq"
)


@activity.defn(name="agents.run_v2.wait_state")
async def wait_state_activity(tenant_id: str, run_id: str, seq: int, kind: str) -> WaitState:
    """The held step's resolution, read from its rows (the signal only wakes the workflow). A
    skipped question with a skip default applies it here, once, and records it (AC-W5)."""
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    if kind in QUESTION_KINDS:
        async with tenant_session(tenant) as session:
            row = (await session.execute(_QUESTION, {"run": run, "seq": seq})).mappings().first()
        if row is None or row["id"] is None:
            return WaitState("expired", "skipped")
        state = str(row["state"])
        if state == "answered":
            return await _settle(tenant, run, row["step_id"], "answered", "succeeded")
        if state == "skipped":
            needs = cast(dict[str, object], row["needs"] or {})
            default = needs.get("skip_default")
            if default is None and not row["skip_default_applied"]:
                return await _settle(tenant, run, row["step_id"], "skipped", "skipped")
            if not row["skip_default_applied"]:
                async with uow(tenant) as tx:
                    await tx.session.execute(
                        text(
                            "UPDATE agent_questions SET skip_default_applied = true, answer = "
                            "coalesce(answer, CAST(:answer AS jsonb)) WHERE id = :id"
                        ),
                        {"answer": json.dumps({"option": default}), "id": row["id"]},
                    )
                    tx.record(
                        "agent_run.skip_default_applied",
                        target=Target("agent_run", run),
                        after=Ref(question=cast(UUID, row["id"])),
                    )
            return await _settle(tenant, run, row["step_id"], "skipped_default", "succeeded")
        if state == "expired":
            return await _settle(tenant, run, row["step_id"], "expired", "skipped")
        return WaitState("open")
    async with tenant_session(tenant) as session:
        row = (await session.execute(_CARD, {"run": run, "seq": seq})).mappings().first()
    if row is None:
        return WaitState("expired", "skipped")
    card = cast(dict[str, object], row["needs"] or {}).get("card_id")
    decided = await card_decision(tenant, UUID(str(card))) if card is not None else None
    if decided is None:
        return WaitState("open")
    return await _settle(tenant, run, row["step_id"], "decided", "succeeded")


async def _settle(
    tenant: TenantContext, run: UUID, step_id: object, resolution: str, state: str
) -> WaitState:
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE agent_run_steps SET state = :state, ended_at = clock_timestamp() "
                "WHERE id = :id AND state IN ('waiting_on_inputs', 'blocked')"
            ),
            {"state": state, "id": step_id},
        )
        tx.record(
            "agent_run_step.finished",
            target=Target("agent_run", run),
            after=Ref(step=cast(UUID, step_id)),
        )
    return WaitState(resolution, state)


@activity.defn(name="agents.run_v2.cancel_held")
async def cancel_held_activity(tenant_id: str, run_id: str) -> int:
    """Stop: the run's open question expires and its held steps are cancelled (a decision card
    stays the reserved person's; deciding it later changes nothing in a stopped run)."""
    tenant = _tenant(tenant_id, run_id)
    run = UUID(run_id)
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE agent_questions SET state = 'expired' "
                "WHERE run_id = :run AND state = 'open'"
            ),
            {"run": run},
        )
        found = await tx.session.execute(
            text(
                "UPDATE agent_run_steps SET state = 'cancelled', ended_at = clock_timestamp() "
                "WHERE run_id = :run AND state IN ('queued', 'dispatched', 'waiting_on_inputs', "
                "'blocked') RETURNING id"
            ),
            {"run": run},
        )
        n = len(found.all())
        tx.record("agent_run.stopped", target=Target("agent_run", run), after=Ref(steps=n))
    return n


# --- the decision.decided consumer (no Temporal: the outbox relay) -------------------------------

_WAITING_ON_CARD: Final = text(
    "SELECT s.run_id FROM agent_run_steps s WHERE s.state = 'blocked' "
    "AND s.needs ->> 'card_id' = :card"
)


async def on_decision_decided(event: OutboxEvent) -> None:
    """AC-W4: the run holding a branch on this card is woken; the workflow reads the decision row
    itself and resumes that branch only."""
    payload = event.payload
    card = str(payload.get("card_id", ""))
    if not card:
        return
    tenant = TenantContext(event.tenant_id, "system", f"{_READER}:decision")
    async with tenant_session(tenant) as session:
        runs = [str(r) for r in (await session.scalars(_WAITING_ON_CARD, {"card": card})).all()]
    for run in runs:
        await signal_workflow(run_workflow_id(str(event.tenant_id), run), DECISION_SIGNAL)


RUN_WAIT_ACTIVITIES: Final = (wait_state_activity, cancel_held_activity)

__all__ = [
    "DECISION_SIGNAL",
    "QUESTION_KINDS",
    "RUN_WAIT_ACTIVITIES",
    "WaitOpened",
    "WaitState",
    "on_decision_decided",
    "open_wait",
    "run_workflow_id",
]
