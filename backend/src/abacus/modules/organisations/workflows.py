"""The consent registry's workflows (T-01-T16; T-01 §4.4; DEC-1354).

Orchestration only, activities by name; no name, figure or document enters the history, only
identifiers and counts. A change to what these schedule lands behind `workflow.patched(...)`;
every history in `tests/workflows/histories/consent-*-v*.json` must keep replaying.

- **ConsentExportWorkflow** (`consent_export:<tenant>:<export>`): one activity builds the CSV
  into a sealed transient bundle (`organisations.consent_export`).
- **ConsentLifecycleSweepWorkflow** (Schedule `consent_sweep:platform`, daily 6:00 AM CT): one
  activity per run sweeps every firm (`organisations.consent_sweep`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

SWEEP_ID = "consent_sweep:platform"
_EXPORT_TIMEOUT = timedelta(minutes=5)
_SWEEP_TIMEOUT = timedelta(minutes=10)
_RETRY = RetryPolicy(maximum_attempts=3)


@dataclass(frozen=True)
class ConsentExportInput:
    tenant_id: str
    export_id: str
    consent_ids: list[str] = field(default_factory=list[str])


def export_workflow_id(tenant_id: str, export_id: str) -> str:
    return f"consent_export:{tenant_id}:{export_id}"


@workflow.defn(name="ConsentExportWorkflow")
class ConsentExportWorkflow:
    """T-01-T16: the C19 CSV, built once (a retried build writes the same keys)."""

    @workflow.run
    async def run(self, request: ConsentExportInput) -> int:
        return await workflow.execute_activity(
            "organisations.consent_export",
            request,
            result_type=int,
            start_to_close_timeout=_EXPORT_TIMEOUT,
            retry_policy=_RETRY,
        )


@workflow.defn(name="ConsentLifecycleSweepWorkflow")
class ConsentLifecycleSweepWorkflow:
    """T-01-T16: once a day, every firm's consents: expiring, expired, register drift."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "organisations.consent_sweep",
            result_type=int,
            start_to_close_timeout=_SWEEP_TIMEOUT,
            retry_policy=_RETRY,
        )
