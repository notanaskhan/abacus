"""The proposals bridge and approved writes (P-10-T38; SPEC-647 AC-P1 to AC-P6, §4.6; ADR P-35,
ADR-161, ADR-005, ADR-090; DEC-24, DEC-3402). PROTECTED (agents).

A run's write waits on a person, and runs only after them:

1. **Held effects.** A proposal kind whose effect is an `approved_write` registers it here
   (`file_save` → `files.save_approved`, matrix action `file.save`). When a person approves such a
   proposal, `proposals.approve_proposal` issues an identity grant in the same unit of work: the
   approver, the action, the proposal as subject, the SHA-256 of exactly the tool call that will
   spend it, `not_before = decided_at + 10 s` (the Undo window) and a 1-hour expiry; the decision
   row names the grant, so `proposal_undo` voids it (AC-P2).
2. **Executor.** `proposal.decided` reaches `on_proposal_event`, which starts one
   `ApprovedWriteWorkflow` per grant (`approved_write:<tenant>:<grant>`, reuse refused). It sleeps
   the Undo window, then its activity calls the tool through C17's runtime (`call_tool`) with the
   grant: the runtime consumes it only after `not_before`, never twice, never voided or expired,
   and only while the approver still holds `file.save` (AC-P3); early, it raises
   `GrantNotYetDue` and the activity retries. Consumed, the copy is filed "<approver> via Agent"
   with `after_ref` = the grant id (AC-P1).
3. **Outcome.** Each decision and Undo re-derives the run's outcome from its proposals' latest
   decisions (AC-P5): any pending → `succeeded` ("Ready for review"); all approved → `approved`;
   all rejected → `rejected`; otherwise `partially_approved` ("3 of 5 approved"). A write that does
   not run records `proposal.write_failed` on the run's stream with its reason
   (`approver_lost_action`, `grant_expired`) and counts nothing; an Undo is `undone`, not a
   failure.

The agent can create suggestions and proposals but never issue, consume for itself or void a grant
(AC-P6): issue is the approving person's (`issue_grant` refuses any other context), consumption is
the runtime's for the one call the grant names, and Undo is the decider's.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.agents.approved_write_workflow import (
    UNDO_WINDOW,
    ApprovedWriteInput,
    ApprovedWriteWorkflow,
    approved_write_id,
)

_READER: Final = "approved-write"
GRANT_LIFETIME: Final = timedelta(hours=1)
OUTCOME_STATES: Final = frozenset({"succeeded", "approved", "partially_approved", "rejected"})
_APPROVED: Final = frozenset({"approved", "approved_with_edits"})
_WRITE_SEQ_BASE: Final = 1_000_000  # write calls' step seq, above any plan step's
_log = get_logger(__name__)


@dataclass(frozen=True)
class HeldEffect:
    """An approved_write a proposal kind's approval holds: the tool, its matrix action."""

    tool: str
    action: str


_HELD: dict[str, HeldEffect] = {}


def register_held_effect(kind: str, effect: HeldEffect) -> None:
    known = _HELD.get(kind)
    if known is not None and known != effect:
        raise ValueError(f"held effect for {kind!r} is already registered")
    _HELD[kind] = effect


def held_effect(kind: str) -> HeldEffect | None:
    return _HELD.get(kind)


def write_arguments(proposal_id: UUID) -> dict[str, object]:
    """The one call a grant pays for: the tool's arguments, canonical."""
    return {"proposal_id": str(proposal_id)}


def write_digest(effect: HeldEffect, proposal_id: UUID) -> str:
    """The grant's payload SHA-256: exactly the runtime's `args_hash` of the call it pays for."""
    canonical = json.dumps(
        {"tool": effect.tool, "args": write_arguments(proposal_id)}, sort_keys=True, default=str
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_seq(proposal_id: UUID) -> int:
    """The write call's step seq (C17's idempotency key with the run and attempt 1)."""
    return _WRITE_SEQ_BASE + int(proposal_id.hex[:7], 16)


def grant_window(decided_at: datetime) -> tuple[datetime, datetime]:
    return decided_at + UNDO_WINDOW, decided_at + UNDO_WINDOW + GRANT_LIFETIME


# --- the outcome (AC-P5) -------------------------------------------------------------------------


def derive_outcome(states: list[str]) -> str:
    """The run's outcome from its proposals' states (pending, approved, approved_with_edits,
    rejected, routed …): any undecided keeps it "Ready for review"."""
    if not states or any(s not in _APPROVED and s != "rejected" for s in states):
        return "succeeded"
    if all(s in _APPROVED for s in states):
        return "approved"
    if all(s == "rejected" for s in states):
        return "rejected"
    return "partially_approved"


def _tenant(tenant_id: UUID, ref: str) -> TenantContext:
    return TenantContext(tenant_id, "system", f"{_READER}:{ref}")


async def rederive_run(tenant_id: UUID, run_id: UUID) -> str | None:
    """Set the run's outcome from its proposals now; None when the run is not in an outcome."""
    from abacus.modules.agents.run_activities import set_state_activity

    tenant = _tenant(tenant_id, str(run_id))
    async with tenant_session(tenant) as session:
        state = await session.scalar(
            text("SELECT state FROM agent_runs WHERE id = :run"), {"run": run_id}
        )
        rows = (
            await session.execute(
                text("SELECT state FROM proposals WHERE agent_run_id = :run"), {"run": run_id}
            )
        ).all()
        pending = await session.scalar(
            text(
                "SELECT count(*) FROM proposals WHERE agent_run_id = :run AND state NOT IN "
                "('approved', 'approved_with_edits', 'rejected')"
            ),
            {"run": run_id},
        )
    if state not in OUTCOME_STATES:
        return None
    outcome = derive_outcome([str(r.state) for r in rows])
    async with uow(tenant) as tx:
        await tx.session.execute(
            text("UPDATE agent_runs SET writes_waiting = :n WHERE id = :run"),
            {"n": int(pending or 0), "run": run_id},
        )
        tx.record(
            "agent_run.writes_counted",
            target=Target("agent_run", run_id),
            after=Ref(waiting=int(pending or 0)),
        )
    if outcome != state:
        await set_state_activity(str(tenant_id), str(run_id), outcome, None, None)
    return outcome


# --- the executor --------------------------------------------------------------------------------


async def _record_write(
    tenant_id: UUID, run_id: UUID, proposal_id: UUID, kind: str, reason: str | None
) -> None:
    """One run-stream row (`proposal.write_saved`, `.write_failed`, `.write_undone`)."""
    tenant = _tenant(tenant_id, str(run_id))
    async with uow(tenant) as tx:
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
                "VALUES (:t, :run, :seq, :type, CAST(:payload AS jsonb))"
            ),
            {
                "t": tenant_id,
                "run": run_id,
                "seq": seq,
                "type": f"proposal.{kind}",
                "payload": json.dumps({"proposal_id": str(proposal_id), "reason": reason}),
            },
        )
        target, after = Target("agent_run", run_id), Ref(proposal=proposal_id, seq=seq)
        if kind == "write_saved":
            tx.record("agent_run.write_saved", target=target, after=after)
        elif kind == "write_undone":
            tx.record("agent_run.write_undone", target=target, after=after)
        else:
            tx.record("agent_run.write_failed", target=target, after=after)


async def execute_approved_write(p: ApprovedWriteInput) -> str:
    """The grant's one call: `saved`, `undone` or the failure reason."""
    from abacus.modules.agents.service import AgentRunNotRunning, load_write_context
    from abacus.modules.agents.tools.runtime import ToolCallIn, call_tool
    from abacus.modules.identity.api import grant_status

    tenant_id, run_id = UUID(p.tenant_id), UUID(p.run_id)
    proposal_id, grant_id = UUID(p.proposal_id), UUID(p.grant_id)
    try:
        agent = await load_write_context(tenant_id, run_id)
    except AgentRunNotRunning:
        await _record_write(tenant_id, run_id, proposal_id, "write_failed", "run_not_writable")
        return "run_not_writable"
    outcome = await call_tool(
        agent,
        ToolCallIn(
            run_id=run_id,
            step_seq=write_seq(proposal_id),
            attempt=1,
            name=p.tool,
            arguments=write_arguments(proposal_id),
            grant_id=grant_id,
        ),
    )
    if outcome.ok:
        await _record_write(tenant_id, run_id, proposal_id, "write_saved", None)
        return "saved"
    status = await grant_status(tenant_id, grant_id)
    if status == "voided":
        await _record_write(tenant_id, run_id, proposal_id, "write_undone", None)
        return "undone"
    reason = {
        "held": "approver_lost_action",
        "expired": "grant_expired",
    }.get(status, str(outcome.code or "write_refused"))
    _log.info("approved_write.refused", run_id=run_id, reason=reason)
    await _record_write(tenant_id, run_id, proposal_id, "write_failed", reason)
    return reason


@activity.defn(name="agents.approved_write.execute")
async def execute_approved_write_activity(p: ApprovedWriteInput) -> str:
    return await execute_approved_write(p)


APPROVED_WRITE_ACTIVITIES: Final = (execute_approved_write_activity,)


# --- the subscriber ------------------------------------------------------------------------------

_PROPOSAL: Final = text(
    "SELECT p.kind, p.agent_run_id, d.decision, d.approval_grant_id FROM proposals p "
    "LEFT JOIN LATERAL (SELECT decision, approval_grant_id FROM proposal_decisions "
    "WHERE proposal_id = p.id ORDER BY created_at DESC, id DESC LIMIT 1) d ON true "
    "WHERE p.id = :id"
)


async def on_proposal_event(event: OutboxEvent) -> None:
    """`proposal.decided` and `proposal.undone`: re-derive the run's outcome; an approval that
    holds an effect starts its executor once."""
    proposal_id = UUID(str(event.payload["proposal_id"]))
    tenant = _tenant(event.tenant_id, str(proposal_id))
    async with tenant_session(tenant) as session:
        row = (await session.execute(_PROPOSAL, {"id": proposal_id})).first()
    if row is None or row.agent_run_id is None:
        return
    run_id = cast(UUID, row.agent_run_id)
    await rederive_run(event.tenant_id, run_id)
    effect = held_effect(str(row.kind))
    if (
        event.event_type != "proposal.decided"
        or effect is None
        or row.decision not in _APPROVED
        or row.approval_grant_id is None
    ):
        return
    grant = str(row.approval_grant_id)
    try:
        await dispatch(
            ApprovedWriteWorkflow,
            ApprovedWriteInput(
                str(event.tenant_id), str(run_id), str(proposal_id), grant, effect.tool
            ),
            id=approved_write_id(str(event.tenant_id), grant),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except WorkflowAlreadyStartedError:
        return


SUBSCRIPTIONS: Final = {
    "proposal.decided": on_proposal_event,
    "proposal.undone": on_proposal_event,
}


def register_file_writes() -> None:
    """`file_save` proposals: the artifact is their target, their effect is held (no applier
    writes at approval: the grant's executor files the copy after the Undo window)."""
    from abacus.kernel.uow import UnitOfWork
    from abacus.modules.agents.file_tools import FILE_SAVE, SAVE, SAVE_TOOL, artifact_engagement
    from abacus.modules.agents.proposal_slots import (
        ApprovedChangeSet,
        register_change_set_applier,
        register_suggestion_target,
    )
    from abacus.modules.identity.api import AuthContext

    async def held(tx: UnitOfWork, person: AuthContext, change: ApprovedChangeSet) -> None:
        del tx, person, change  # the effect waits on the grant; nothing is written now

    register_suggestion_target("run_artifact", engagement_of=artifact_engagement)
    register_change_set_applier(FILE_SAVE, held)
    register_held_effect(FILE_SAVE, HeldEffect(SAVE_TOOL, SAVE))
