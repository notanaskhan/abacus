"""Starting screening from relayed events (TASK-011 design §7). PROTECTED.

The relay (at least once) hands each `evidence_version.created` to `start_screening`, which
starts `screening:<tenant_id>:<evidence_version_id>` (tenant-qualified: Temporal's namespace is
shared by every firm). There is no execution timeout: each activity has its own, and the run is
always ended by `screening.fail_run`, so a run never stays `running` because the workflow was
killed. A redelivery attaches to the running workflow or finds
it finished: either way the event counts as delivered. `requested_by` comes only from the event,
which the evidence module writes in the same transaction as the version.
"""

from __future__ import annotations

from contextlib import suppress
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.dispatch import dispatch
from abacus.kernel.uow import OutboxEvent
from abacus.modules.agents.workflow_types import ScreeningInput
from abacus.modules.agents.workflows import ScreeningWorkflow
from abacus.modules.evidence.api import EvidenceVersionCreated

EVIDENCE_VERSION_CREATED = EvidenceVersionCreated.event_type


def workflow_id(tenant_id: UUID, evidence_version_id: UUID) -> str:
    return f"screening:{tenant_id}:{evidence_version_id}"


def screening_input(event: OutboxEvent) -> ScreeningInput:
    """The workflow input, from the event's identifiers only (a malformed event raises: the relay
    backs it off and eventually parks it)."""
    version = UUID(str(event.payload["evidence_version_id"]))
    requested = event.payload.get("requested_by")
    return ScreeningInput(
        str(event.tenant_id),
        str(version),
        str(event.event_id),
        str(UUID(str(requested))) if requested is not None else None,
    )


async def start_screening(event: OutboxEvent) -> None:
    input = screening_input(event)
    # Already screened (or screening): the event counts as delivered.
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            ScreeningWorkflow,
            input,
            id=workflow_id(event.tenant_id, UUID(input.evidence_version_id)),
            # A failed workflow may be started again by a redelivery; a finished one may not.
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


SUBSCRIPTIONS = {EVIDENCE_VERSION_CREATED: start_screening}
