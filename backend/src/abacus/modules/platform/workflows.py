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

import asyncio
from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.platform.workflow_types import (
        CanaryInput,
        CanaryOutcome,
        CanaryPlan,
        CanaryResult,
        IncidentPropagationInput,
        IncidentPropagationOutcome,
        IncidentPropagationResult,
        IncidentPropagationStep,
        IncidentStepResult,
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


# v2 (security review, S7): every firm is its own branch. A firm whose step fails every attempt
# (or fails non-retryably, such as changed facts) is named in the result and in the finishing
# record, and the other firms are written anyway: one bad firm never holds back the 72-hour
# notice to the rest. Steps run in batches so a long-retrying firm delays only its batch.
INCIDENT_ISOLATED_PATCH: Final = "incident_isolated_v2"
_INCIDENT_BATCH: Final = 25
_INCIDENT_STEP_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=12,
    non_retryable_error_types=["FirmNotFound", "IncidentFactsChanged"],
)


@workflow.defn(name="IncidentPropagation")
class IncidentPropagationWorkflow:
    """Q-02-T33 (RB-27): `incident_propagate:<accrued_ref>` writes Accrued's facts into each named
    firm's register as the system. Each step is repeat-safe (one entry per firm and Accrued
    reference, the same facts), so a rerun converges.

    v1 (recorded history `incident-propagation-v1-three-firms.json`): one firm at a time, and a
    firm that failed ended the run. v2 (`incident_isolated_v2`): per-firm isolation, then
    `platform.finish_incident_propagation` records the outcome with the failed firms."""

    @workflow.run
    async def run(self, given: IncidentPropagationInput) -> IncidentPropagationResult:
        if not workflow.patched(INCIDENT_ISOLATED_PATCH):
            refs: list[IncidentStepResult] = []
            for tenant_id in given.tenant_ids:
                ref = await workflow.execute_activity(
                    "platform.propagate_incident",
                    IncidentPropagationStep(
                        given.accrued_ref,
                        tenant_id,
                        given.facts,
                        given.staff_id,
                        given.reason_sha256,
                    ),
                    result_type=str,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_INCIDENT_RETRY,
                )
                refs.append(IncidentStepResult(tenant_id, ref, "written"))
            return IncidentPropagationResult(tuple(refs))

        async def one(tenant_id: str) -> IncidentStepResult | None:
            try:
                return await workflow.execute_activity(
                    "platform.propagate_incident_v2",
                    IncidentPropagationStep(
                        given.accrued_ref,
                        tenant_id,
                        given.facts,
                        given.staff_id,
                        given.reason_sha256,
                    ),
                    result_type=IncidentStepResult,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_INCIDENT_STEP_RETRY,
                )
            except ActivityError:
                return None

        done: list[IncidentStepResult] = []
        failed: list[str] = []
        firms = list(given.tenant_ids)
        for start in range(0, len(firms), _INCIDENT_BATCH):
            batch = firms[start : start + _INCIDENT_BATCH]
            results = await asyncio.gather(*(one(t) for t in batch))
            for tenant_id, result in zip(batch, results, strict=True):
                if result is None:
                    failed.append(tenant_id)
                else:
                    done.append(result)
        await workflow.execute_activity(
            "platform.finish_incident_propagation",
            IncidentPropagationOutcome(
                accrued_ref=given.accrued_ref,
                staff_id=given.staff_id,
                reason_sha256=given.reason_sha256,
                firms=len(firms),
                written=sum(1 for r in done if r.status == "written"),
                identical=sum(1 for r in done if r.status == "identical"),
                failed_tenant_ids=tuple(failed),
            ),
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        return IncidentPropagationResult(tuple(done), tuple(failed))


# Q-01-T26 (SPEC-007 AC-6): the hourly spend-anomaly pass, one per run on a Schedule.
SPEND_ANOMALY_ID: Final = "spend_anomaly:platform"
_JOB_TIMEOUT = timedelta(minutes=5)
_JOB_RETRY = RetryPolicy(maximum_attempts=3)  # a failed hour is retried by the next run


@workflow.defn(name="SpendAnomaly")
class SpendAnomalyWorkflow:
    """`spend_anomaly:platform`: flag engagements spending past the anomaly multiple (it alerts,
    never blocks). Started only by its Schedule (overlap SKIP), so two workers never flag twice."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "platform.flag_spend_anomalies",
            result_type=int,
            start_to_close_timeout=_JOB_TIMEOUT,
            retry_policy=_JOB_RETRY,
        )


# --- Q-01-T30: the canary ----------------------------------------------------------------------

CANARY_EVERY: Final = timedelta(minutes=15)
_CANARY_STEP_TIMEOUT = timedelta(seconds=60)
_CANARY_WAIT_TIMEOUT = timedelta(minutes=3)  # SLO-03: upload to preview within 2 minutes
_CANARY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_attempts=3,
    non_retryable_error_types=["CanaryNotSynthetic", "CanaryStepFailed"],
)
_CANARY_ONCE = RetryPolicy(maximum_attempts=1)  # a wait or a check is not repeated within a run
_CANARY_REPORT_RETRY = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=5)


def canary_workflow_id(tenant_id: str) -> str:
    return f"canary:{tenant_id}"


def _canary_code(error: ActivityError) -> str:
    """The failed step's code: the probe's own, `timeout`, or `error` (never an error text)."""
    cause = error.cause
    if isinstance(cause, ApplicationError) and cause.type in ("CanaryStepFailed",):
        return cause.message
    if isinstance(cause, ApplicationError) and cause.type == "CanaryNotSynthetic":
        return "not_synthetic"
    if isinstance(cause, TimeoutError):
        return "timeout"
    return "error"


@workflow.defn(name="Canary")
class CanaryWorkflow:
    """`canary:<tenant>` (Q-01-T30): the end-to-end probe, every 15 minutes on its Schedule. The
    steps stop at the first failure; the report always runs, so every run counts and pages are
    decided on the run's outcome."""

    @workflow.run
    async def run(self, given: CanaryInput) -> CanaryResult:
        step = "prepare"
        route: str | None = None
        try:
            plan = await workflow.execute_activity(
                "canary.prepare",
                given,
                result_type=CanaryPlan,
                start_to_close_timeout=_CANARY_STEP_TIMEOUT,
                retry_policy=_CANARY_RETRY,
            )
            step = "create_item"
            item = await workflow.execute_activity(
                "canary.create_item",
                plan,
                result_type=str,
                start_to_close_timeout=_CANARY_STEP_TIMEOUT,
                retry_policy=_CANARY_RETRY,
            )
            step = "upload"
            version = await workflow.execute_activity(
                "canary.upload",
                args=[plan, item],
                result_type=str,
                start_to_close_timeout=_CANARY_STEP_TIMEOUT,
                retry_policy=_CANARY_ONCE,  # a retried upload would be a duplicate
            )
            step = "wait_processing"
            await workflow.execute_activity(
                "canary.wait_processing",
                args=[plan, item, version],
                start_to_close_timeout=_CANARY_WAIT_TIMEOUT,
                retry_policy=_CANARY_ONCE,
            )
            step = "screen"
            route = await workflow.execute_activity(
                "canary.screen",
                args=[plan, item, version],
                result_type=str,
                start_to_close_timeout=_CANARY_WAIT_TIMEOUT,
                retry_policy=_CANARY_ONCE,
            )
            step = "observe_outbox"
            await workflow.execute_activity(
                "canary.observe_outbox",
                args=[plan, version],
                start_to_close_timeout=_CANARY_STEP_TIMEOUT,
                retry_policy=_CANARY_ONCE,
            )
            step = "send_simulator"
            await workflow.execute_activity(
                "canary.send_simulator",
                plan,
                start_to_close_timeout=_CANARY_STEP_TIMEOUT,
                retry_policy=_CANARY_RETRY,
            )
            outcome = CanaryOutcome(given.tenant_id, True, None, None, route)
        except ActivityError as error:
            outcome = CanaryOutcome(given.tenant_id, False, step, _canary_code(error), route)
        return await workflow.execute_activity(
            "canary.report",
            outcome,
            result_type=CanaryResult,
            start_to_close_timeout=_CANARY_STEP_TIMEOUT,
            retry_policy=_CANARY_REPORT_RETRY,
        )
