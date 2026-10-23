"""Record the tenant provisioning workflow's replay history (Q-01-T45; ADR-156, ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_tenant_provisioning <output-directory> [version]

Records the real `TenantProvisioningWorkflow` against throwaway containers with its activity
replaced by a stub (replay never runs activities):
- `tenant-provisioning-<version>-provisioned.json`: `tenant.provisioned` is recorded.
Synthetic values only (a `.test` sink address, a made-up operator handle). Refuses to overwrite an
existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.platform.api import (
    ProvisionTenantInput,
    TenantProvisioningWorkflow,
    provisioning_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_NAMES = ("provisioned",)


@activity.defn(name="platform.emit_tenant_provisioned")
async def _emit(given: ProvisionTenantInput) -> str:
    return "none"


async def _run(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        TenantProvisioningWorkflow.run,
        ProvisionTenantInput(
            tenant_id=_TENANT,
            slug="canary-co",
            synthetic=True,
            plan="pilot",
            admins=("admin@sink.example.test",),
            idempotency_key="provision-example-canary-1",
            operator="recorder",
        ),
        id=provisioning_workflow_id(_TENANT),
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[TenantProvisioningWorkflow], activities=[_emit]
    ):
        scrubbed = await decoded_and_scrubbed(await _run(client), payload_codec())
        path = out / f"tenant-provisioning-{version}-provisioned.json"
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"tenant-provisioning-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
