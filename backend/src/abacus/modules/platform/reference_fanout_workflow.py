"""ReferenceSetFanOutWorkflow (K-02-T12; K-02 §4.6; SPEC-500 AC-49 to AC-51).

Orchestration only, activities by name, identifiers only in the history (the version id and
tenant ids; never a rule's value). One run per published or withdrawn version
(`reference_fanout:<action>:<version>`, background class): the owner-role CLI passes the active
tenants and the handles in, and the run fans `platform.reference_set_announce` out per tenant,
each idempotent on (tenant, version), so a re-run or a retried activity writes nothing
twice. Changes land behind `workflow.patched(...)`;
`tests/workflows/histories/reference-fanout-v1-*.json` must keep replaying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

_STEP = timedelta(seconds=60)
_RETRY = RetryPolicy(maximum_attempts=5, maximum_interval=timedelta(minutes=2))


@dataclass(frozen=True)
class FanOutInput:
    """Everything the run needs, read by the owner-role CLI (the worker's app role has no grant
    on 0400's tables or `active_tenant_ids()`): handles and keys, never a rule's value."""

    version_id: str
    action: str  # "published" or "withdrawn"
    set_key: str = ""
    operator: str = ""
    approver: str = ""
    tenant_ids: list[str] = field(default_factory=list[str])


def fanout_workflow_id(version_id: str, action: str) -> str:
    return f"reference_fanout:{action}:{version_id}"


@workflow.defn(name="ReferenceSetFanOutWorkflow")
class ReferenceSetFanOutWorkflow:
    @workflow.run
    async def run(self, request: FanOutInput) -> int:
        announced = 0
        for tenant_id in request.tenant_ids:
            wrote: bool = await workflow.execute_activity(
                "platform.reference_set_announce",
                args=[tenant_id, request],
                result_type=bool,
                start_to_close_timeout=_STEP,
                retry_policy=_RETRY,
            )
            announced += int(wrote)
        return announced
