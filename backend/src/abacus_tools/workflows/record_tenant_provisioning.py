"""Record the tenant provisioning workflow's replay history (Q-01-T45; ADR-156, ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_tenant_provisioning <output-directory> [version]

Records the real `TenantProvisioningWorkflow` against throwaway containers with its activity
replaced by a stub (replay never runs activities):
- `tenant-provisioning-<version>-provisioned.json`: `tenant.provisioned` is recorded; from v2,
  after the plan's entitlements and the first administrators' invitations.
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
    TenantKeyInput,
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    provisioning_workflow_id,
    tenant_key_workflow_id,
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


@activity.defn(name="platform.set_plan_entitlements")  # v2 (migration 0107)
async def _entitle(given: ProvisionTenantInput) -> int:
    return 2


@activity.defn(name="platform.invite_first_admins")  # v2 (migration 0107)
async def _invite(given: ProvisionTenantInput) -> int:
    return len(given.admins)


@activity.defn(name="platform.request_tenant_key")  # v3 (Q-01-T27)
async def _request_key(given: ProvisionTenantInput) -> bool:
    return True


_KEY_ARN = "arn:aws:kms:us-east-2:000000000000:key/mrk-recorder"


@activity.defn(name="keyops.create_tenant_key")
async def _create_key(given: TenantKeyInput) -> str:
    return _KEY_ARN


@activity.defn(name="keyops.replicate_tenant_key")
async def _replicate_key(given: TenantKeyInput, key_arn: str) -> str:
    return key_arn.replace("us-east-2", "us-west-2")


@activity.defn(name="keyops.verify_tenant_key")
async def _verify_key(given: TenantKeyInput, key_arn: str, replica_arn: str) -> str:
    return "replica_verified"


async def _run_key(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        TenantKeyWorkflow.run,
        TenantKeyInput(_TENANT, "recorder"),
        id=tenant_key_workflow_id(_TENANT),
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


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
        client,
        task_queue=_TASK_QUEUE,
        workflows=[TenantProvisioningWorkflow, TenantKeyWorkflow],
        activities=[
            _emit,
            _entitle,
            _invite,
            _request_key,
            _create_key,
            _replicate_key,
            _verify_key,
        ],
    ):
        scrubbed = await decoded_and_scrubbed(await _run(client), payload_codec())
        path = out / f"tenant-provisioning-{version}-provisioned.json"
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")
        if version != "v1" and version != "v2":  # the key workflow exists from v3 (Q-01-T27)
            key = await decoded_and_scrubbed(await _run_key(client), payload_codec())
            key_path = out / "tenant-key-v1-verified.json"
            if not key_path.exists():
                key_path.write_text(key.to_json())
                print(f"recorded {key_path}")


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
