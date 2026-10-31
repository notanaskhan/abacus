"""Starting the matcher's intake mode (N-01-T22; N-01 §6). PROTECTED.

`inbox_attachment.matchable` (communications: a classified attachment of a known client, or each
classified one when its thread is matched) starts `InboxMatchIntakeWorkflow` when
`matching.firm_intake` is on and a real model route exists; the run's own gates
(`intake_match.create_intake_match_run`) decide the rest. One run per attachment and client:
`inbox_match_intake:<tenant>:<attachment>:<client>`, so a redelivery attaches to it and a
re-match to another client starts afresh.
"""

from __future__ import annotations

from contextlib import suppress
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent
from abacus.modules.agents.inbox_match import MATCHER, model_available
from abacus.modules.agents.spec import spec
from abacus.modules.agents.workflow_types import IntakeMatchInput
from abacus.modules.agents.workflows import InboxMatchIntakeWorkflow

_log = get_logger(__name__)
WORKFLOWS: dict[type, WorkClass] = {InboxMatchIntakeWorkflow: spec(MATCHER).work_class}
register_work_classes(WORKFLOWS)


def workflow_id(tenant_id: UUID, attachment_id: UUID, client_id: UUID) -> str:
    return f"inbox_match_intake:{tenant_id}:{attachment_id}:{client_id}"


async def start_intake_match(event: OutboxEvent) -> None:
    tenant = TenantContext(event.tenant_id, "system", "agents.inbox_match_intake")
    if not await flag_enabled(tenant, _flags.MATCHING_FIRM_INTAKE):
        return
    if not model_available():
        _log.info("inbox_match_intake.skipped", tenant_id=event.tenant_id, reason="no_model")
        return
    attachment_id = UUID(str(event.payload["attachment_id"]))
    client_id = UUID(str(event.payload["client_id"]))
    given = IntakeMatchInput(
        str(event.tenant_id), str(attachment_id), str(client_id), str(event.event_id)
    )
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            InboxMatchIntakeWorkflow,
            given,
            id=workflow_id(event.tenant_id, attachment_id, client_id),
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
