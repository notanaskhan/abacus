"""Starting the legal-hold workflows and the inheritance consumer (Q-02-T29; ADR-017, ADR-071).

- `legal_hold.placed` starts `LegalHoldApply` as `legal_hold_apply:<tenant>:<hold>`, and
  `legal_hold.lifted` starts `LegalHoldRelease` as `legal_hold_release:<tenant>:<hold>`, both on
  the batch class. One run per hold: a redelivered event attaches to it or finds it done.
- `evidence_version.created` sets the S3 hold for a new version its own transaction counted
  (`inherit_holds`; the plan's HoldInherit is this consumer, not a workflow).
"""

from __future__ import annotations

from contextlib import suppress
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.uow import Handler, OutboxEvent
from abacus.modules.evidence.events import LegalHoldLifted, LegalHoldPlaced
from abacus.modules.evidence.holds import apply_version_holds
from abacus.modules.evidence.workflow_types import LegalHoldInput
from abacus.modules.evidence.workflows import LegalHoldApply, LegalHoldRelease

WORKFLOWS: dict[type, WorkClass] = {LegalHoldApply: "batch", LegalHoldRelease: "batch"}
register_work_classes(WORKFLOWS)


def apply_workflow_id(tenant_id: UUID, hold_id: UUID) -> str:
    return f"legal_hold_apply:{tenant_id}:{hold_id}"


def release_workflow_id(tenant_id: UUID, hold_id: UUID) -> str:
    return f"legal_hold_release:{tenant_id}:{hold_id}"


async def _start(workflow: type, workflow_id: str, given: LegalHoldInput) -> None:
    # A redelivery for a run that already finished counts as delivered.
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            workflow,
            given,
            id=workflow_id,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


async def on_hold_placed(event: OutboxEvent) -> None:
    hold = UUID(str(event.payload["hold_id"]))
    await _start(
        LegalHoldApply,
        apply_workflow_id(event.tenant_id, hold),
        LegalHoldInput(str(event.tenant_id), str(hold)),
    )


async def on_hold_lifted(event: OutboxEvent) -> None:
    hold = UUID(str(event.payload["hold_id"]))
    await _start(
        LegalHoldRelease,
        release_workflow_id(event.tenant_id, hold),
        LegalHoldInput(str(event.tenant_id), str(hold)),
    )


async def on_version_created(event: OutboxEvent) -> None:
    """Set the S3 hold for every hold object the new version's transaction wrote."""
    await apply_version_holds(event.tenant_id, UUID(str(event.payload["evidence_version_id"])))


def with_hold_inheritance(handler: Handler) -> Handler:
    """`evidence_version.created` already has a subscriber in this module (upload processing):
    the S3 hold comes first, then the existing handler."""

    async def both(event: OutboxEvent) -> None:
        await on_version_created(event)
        await handler(event)

    return both


SUBSCRIPTIONS: dict[str, Handler] = {
    LegalHoldPlaced.event_type: on_hold_placed,
    LegalHoldLifted.event_type: on_hold_lifted,
}
