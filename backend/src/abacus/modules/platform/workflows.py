"""Tenant provisioning (Q-01-T45; ADR-156, P-65; ADR-017, ADR-090). PROTECTED.

Orchestration only: activities by name. Started by `abacus_tools.tenants provision` after
`provision_firm(...)` created the firm, as `tenant_provision:<tenant_id>` on the background
class; the same idempotency key returns the same tenant, and the id policy starts no second run.

Patch points. Each step that is not in v1 lands with its own change, behind its own
`workflow.patched(...)` id and before `emit_tenant_provisioned`, so the recorded v1 history
(`tenant-provisioning-v1-provisioned.json`) keeps replaying:

- `KMS_CHILD_PATCH`: the child `TenantKeyWorkflow` (`tenant_key:<tenant_id>`, keyops queue)
  arrives with Q-01-T27. Until then a provisioned firm keeps `kms_key_status = 'none'`, and a firm
  without a `replica_verified` key stores no client content (ADR-156).
- `PLAN_ENTITLEMENTS_PATCH` (on, migration 0107): `set_plan_entitlements` writes the plan's
  modules (`plan_modules`) through `apply_plan_entitlements`, for a newly provisioned firm only.
- `FIRST_ADMINS_PATCH` (on, migration 0107): `invite_first_admins` issues operator-sent staff
  invitations through `invite_first_admin`, while the firm has no member.
- `G04_PLAN_PATCH`: G-04's console plan step (`g04_plan_v2`).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.platform.workflow_types import ProvisionTenantInput, ProvisionTenantResult

KMS_CHILD_PATCH: Final = "tenant_key_v1"
PLAN_ENTITLEMENTS_PATCH: Final = "plan_entitlements_v1"
FIRST_ADMINS_PATCH: Final = "first_admins_v1"
G04_PLAN_PATCH: Final = "g04_plan_v2"

_TIMEOUT = timedelta(seconds=30)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=10,
    non_retryable_error_types=["FirmNotFound"],
)


def provisioning_workflow_id(tenant_id: str) -> str:
    return f"tenant_provision:{tenant_id}"


@workflow.defn(name="TenantProvisioning")
class TenantProvisioningWorkflow:
    @workflow.run
    async def run(self, input: ProvisionTenantInput) -> ProvisionTenantResult:
        # v2 (0107): the plan's entitlements, then the first administrators' invitations. A v1
        # history (no markers) replays without them.
        rows = invited = 0
        if workflow.patched(PLAN_ENTITLEMENTS_PATCH):
            rows = await workflow.execute_activity(
                "platform.set_plan_entitlements",
                input,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        if workflow.patched(FIRST_ADMINS_PATCH):
            invited = await workflow.execute_activity(
                "platform.invite_first_admins",
                input,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        # v1: provision_firm created the firm; record it as provisioned, by the operator.
        key_status = await workflow.execute_activity(
            "platform.emit_tenant_provisioned",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        return ProvisionTenantResult(input.tenant_id, key_status, rows, invited)
