"""Tenant provisioning (Q-01-T45; ADR-156, P-65; ADR-017, ADR-090). PROTECTED.

Orchestration only: activities by name. Started by `abacus_tools.tenants provision` after
`provision_firm(...)` created the firm, as `tenant_provision:<tenant_id>` on the background
class; the same idempotency key returns the same tenant, and the id policy starts no second run.

Patch points. Each step that is not in v1 lands with its own change, behind its own
`workflow.patched(...)` id and before `emit_tenant_provisioned`, so the recorded v1 history
(`tenant-provisioning-v1-provisioned.json`) keeps replaying:

- `KMS_CHILD_PATCH` (on, Q-01-T27): `platform.request_tenant_key` starts `TenantKeyWorkflow`
  (`tenant_key:<tenant_id>`) on the keyops queue through `kernel.dispatch`. It is a separate run,
  not a child, because a workflow module never names a task queue (DISPATCH-001). Provisioning
  doesn't wait for the key: a firm without a `replica_verified` key stores no client content
  (ADR-156), so the gate holds until the key run ends.
- `PLAN_ENTITLEMENTS_PATCH` (on, migration 0107): `set_plan_entitlements` writes the plan's
  modules (`plan_modules`) through `apply_plan_entitlements`, for a newly provisioned firm only.
- `FIRST_ADMINS_PATCH` (on, migration 0107): `invite_first_admins` issues operator-sent staff
  invitations through `invite_first_admin`, while the firm has no member.
- `RETENTION_DEFAULTS_PATCH` (on, migration 0112, Q-02-T23): `apply_retention_defaults` gives
  the new firm a retention policy per published default (`retention_apply_defaults`). Before the
  default set is published it applies nothing and the floors govern.
- `G04_PLAN_PATCH`: G-04's console plan step (`g04_plan_v2`).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.platform.workflow_types import (
        IncidentPropagationInput,
        IncidentPropagationStep,
        ProvisionTenantInput,
        ProvisionTenantResult,
        TenantKeyInput,
    )

KMS_CHILD_PATCH: Final = "tenant_key_v1"
PLAN_ENTITLEMENTS_PATCH: Final = "plan_entitlements_v1"
FIRST_ADMINS_PATCH: Final = "first_admins_v1"
RETENTION_DEFAULTS_PATCH: Final = "retention_defaults_v1"
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
        # v3 (Q-01-T27): the tenant key, on the keyops queue; this run never holds CreateKey.
        if workflow.patched(KMS_CHILD_PATCH):
            await workflow.execute_activity(
                "platform.request_tenant_key",
                input,
                result_type=bool,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        # v4 (Q-02-T23): the published default retention policies.
        if workflow.patched(RETENTION_DEFAULTS_PATCH):
            await workflow.execute_activity(
                "platform.apply_retention_defaults",
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


def tenant_key_workflow_id(tenant_id: str) -> str:
    return f"tenant_key:{tenant_id}"


# A replica that doesn't verify yet (KMS replication is eventually consistent) is retried for a
# while; a firm that doesn't exist is never retried.
_KEY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=20,
    non_retryable_error_types=["FirmNotFound"],
)


@workflow.defn(name="TenantKey")
class TenantKeyWorkflow:
    """Q-01-T27 (P-65): create, replicate and verify one firm's tenant key, on the keyops queue.
    Every step is idempotent, so a rerun converges on the same key."""

    @workflow.run
    async def run(self, given: TenantKeyInput) -> str:
        key_arn = await workflow.execute_activity(
            "keyops.create_tenant_key",
            given,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_KEY_RETRY,
        )
        replica_arn = await workflow.execute_activity(
            "keyops.replicate_tenant_key",
            args=[given, key_arn],
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_KEY_RETRY,
        )
        return await workflow.execute_activity(
            "keyops.verify_tenant_key",
            args=[given, key_arn, replica_arn],
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_KEY_RETRY,
        )


def incident_propagation_workflow_id(accrued_ref: str) -> str:
    return f"incident_propagate:{accrued_ref}"


# The DPA's 72-hour notice: retry briskly and for a long time; a firm that doesn't exist is
# never retried (staff follow RB-27's manual step for it).
_INCIDENT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=50,
    non_retryable_error_types=["FirmNotFound"],
)


@workflow.defn(name="IncidentPropagation")
class IncidentPropagationWorkflow:
    """Q-02-T33 (RB-27): `incident_propagate:<accrued_ref>` writes Accrued's facts into each named
    firm's register as the system, one firm per activity, in the order given. Each step is
    repeat-safe (one entry per firm and Accrued reference), so a rerun converges. Returns the
    firms' entry references."""

    @workflow.run
    async def run(self, given: IncidentPropagationInput) -> list[str]:
        refs: list[str] = []
        for tenant_id in given.tenant_ids:
            ref = await workflow.execute_activity(
                "platform.propagate_incident",
                IncidentPropagationStep(
                    given.accrued_ref, tenant_id, given.facts, given.staff_id, given.reason_sha256
                ),
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_INCIDENT_RETRY,
            )
            refs.append(ref)
        return refs
