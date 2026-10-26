"""The daily audit-chain anchor (Q-02-T21; C-09, ADR-016): each firm's newest checkpoint hash
is published to the records bucket in COMPLIANCE mode for seven years (`records.anchor_chain`),
on the Schedule `audit_anchor:platform` (overlap SKIP). `AuditAnchorWorkflow` (in
`workflows.py`) orchestrates the activity by name; one firm's failure is logged and the others
still anchor.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import activity

from abacus.kernel.clock import system_now
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.modules.evidence.records import anchor_chain
from abacus.modules.evidence.workflows import ANCHOR_ID, AuditAnchorWorkflow
from abacus.modules.identity.api import firm_tenant_ids

ANCHOR_RETENTION: Final = timedelta(days=7 * 365 + 2)  # seven years, with the leap days
_log = get_logger(__name__)


@activity.defn(name="evidence.anchor_chains")
async def anchor_chains_activity() -> int:
    anchored = 0
    retain_until = system_now() + ANCHOR_RETENTION
    for tenant in await firm_tenant_ids():
        try:
            if await anchor_chain(tenant, retain_until) is not None:
                anchored += 1
        except Exception as exc:
            _log.error("audit_anchor.failed", tenant_id=str(tenant), error=type(exc).__name__)
    return anchored


WORKFLOWS: dict[type, WorkClass] = {AuditAnchorWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (anchor_chains_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=ANCHOR_ID,
        workflow=AuditAnchorWorkflow,
        every=timedelta(days=1),
        note="Q-02-T21: anchor each firm's newest checkpoint in the records bucket (COMPLIANCE)",
    ),
)
