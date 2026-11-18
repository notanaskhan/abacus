"""`IntegrationHealthWorkflow` (W-01-T13 rest; W-01 §3 F4; SPEC-659 AC-27, AC-28; DEC-5333; red).

A platform Schedule every 15 minutes over every firm's connected and needs-attention firm
installs. Each install's Connect port answers `check_health` (read only, its own declared host);
a transient answer is retried in the same tick up to `FAILURES_TO_ATTENTION` times, so "three
server errors or timeouts in a row" needs no stored count. The outcome goes through `apply_probe`
(the rule, one unit of work only when something changes, the outbox event the firm admins'
`connection_needs_reauth` notification follows). No install whose port is not registered here is
probed (fail-closed); one firm's or install's failure never stops the rest.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.dispatch import PlatformSchedule
    from abacus.kernel.logging import get_logger
    from abacus.modules.integrations.health_probe import probe_tenant

_log = get_logger(__name__)
SWEEP_ID: Final = "integration_health:platform"


@activity.defn(name="integrations.health_sweep")
async def health_sweep_activity() -> int:
    from abacus.modules.identity.api import firm_tenant_ids

    probed = 0
    for tenant_id in await firm_tenant_ids():
        try:
            probed += await probe_tenant(tenant_id)
        except Exception as exc:  # one firm's failure is logged; the sweep goes on
            _log.error(
                "integration.health_sweep_failed",
                tenant_id=str(tenant_id),
                error=type(exc).__name__,
            )
    return probed


@workflow.defn(name="IntegrationHealthWorkflow")
class IntegrationHealthWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "integrations.health_sweep",
            result_type=int,
            start_to_close_timeout=timedelta(minutes=14),
            retry_policy=RetryPolicy(maximum_attempts=1),  # the next tick is the retry
        )


WORKFLOWS: Final[dict[type, str]] = {IntegrationHealthWorkflow: "batch"}
ACTIVITIES: Final[tuple[object, ...]] = (health_sweep_activity,)
SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=SWEEP_ID,
        workflow=IntegrationHealthWorkflow,
        every=timedelta(minutes=15),
        note="W-01-T13: probe every live firm token install; a refused token is Needs reauth",
    ),
)
