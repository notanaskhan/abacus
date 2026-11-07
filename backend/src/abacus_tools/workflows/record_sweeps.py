"""Record the replay histories of the client import and four scheduled sweeps (Q-03-T195;
ADR-090). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_sweeps <output-directory> [version]

Each runs for real against throwaway containers with its activities replaced by stubs (replay never
runs activities):
- `client-import-<v>-applied.json` and `-failed.json`: the rows apply and the import completes, or
  the apply fails and the import is marked failed;
- `client-import-erase-<v>-erased.json`, `connection-health-<v>-checked.json`,
  `evidence-integrity-<v>-swept.json`, `pilot-metrics-<v>-snapshotted.json`: one pass each.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.connections.workflows import ConnectionHealthWorkflow
from abacus.modules.engagements.workflows import (
    ClientImportEraseWorkflow,
    ClientImportInput,
    ClientImportWorkflow,
)
from abacus.modules.platform.workflows import PilotMetricsWorkflow
from abacus.modules.signatures.workflows import EvidenceIntegrityWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE: Final = "abacus-recorder"
_TENANT: Final = "00000000-0000-4000-8000-000000000001"
_APPLIES: Final = "00000000-0000-4000-8000-0000000000a1"
_FAILS: Final = "00000000-0000-4000-8000-0000000000a2"
_NAMES: Final = (
    "client-import-{v}-applied",
    "client-import-{v}-failed",
    "client-import-erase-{v}-erased",
    "connection-health-{v}-checked",
    "evidence-integrity-{v}-swept",
    "pilot-metrics-{v}-snapshotted",
)


@activity.defn(name="client_import.apply")
async def _apply(given: ClientImportInput) -> int:
    if given.import_id == _FAILS:
        raise ApplicationError("synthetic failure", non_retryable=True)
    return 12


@activity.defn(name="client_import.complete")
async def _complete(given: ClientImportInput) -> str:
    del given
    return "completed"


@activity.defn(name="client_import.mark_failed")
async def _mark_failed(given: ClientImportInput) -> str:
    del given
    return "failed"


@activity.defn(name="client_import.erase_files")
async def _erase() -> int:
    return 2


@activity.defn(name="connections.check_connection_health")
async def _health() -> int:
    return 3


@activity.defn(name="signatures.evidence_integrity_sweep")
async def _integrity() -> int:
    return 5


@activity.defn(name="platform.pilot_metrics")
async def _pilot() -> int:
    return 1


async def _histories(client: Client) -> list[tuple[str, WorkflowHistory]]:
    """Each run, in `_NAMES` order, by its typed `run` method."""
    out: list[tuple[str, WorkflowHistory]] = []
    for name, import_id in ((_NAMES[0], _APPLIES), (_NAMES[1], _FAILS)):
        handle = await client.start_workflow(
            ClientImportWorkflow.run,
            ClientImportInput(_TENANT, import_id),
            id=f"rec-client-import-{import_id[-2:]}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        out.append((name, await handle.fetch_history()))
    erase = await client.start_workflow(
        ClientImportEraseWorkflow.run, id="rec-erase", task_queue=_TASK_QUEUE
    )
    await erase.result()
    out.append((_NAMES[2], await erase.fetch_history()))
    health = await client.start_workflow(
        ConnectionHealthWorkflow.run, id="rec-health", task_queue=_TASK_QUEUE
    )
    await health.result()
    out.append((_NAMES[3], await health.fetch_history()))
    integrity = await client.start_workflow(
        EvidenceIntegrityWorkflow.run, id="rec-integrity", task_queue=_TASK_QUEUE
    )
    await integrity.result()
    out.append((_NAMES[4], await integrity.fetch_history()))
    pilot = await client.start_workflow(
        PilotMetricsWorkflow.run, id="rec-pilot", task_queue=_TASK_QUEUE
    )
    await pilot.result()
    out.append((_NAMES[5], await pilot.fetch_history()))
    return out


async def _record_all(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[
            ClientImportWorkflow,
            ClientImportEraseWorkflow,
            ConnectionHealthWorkflow,
            EvidenceIntegrityWorkflow,
            PilotMetricsWorkflow,
        ],
        activities=[_apply, _complete, _mark_failed, _erase, _health, _integrity, _pilot],
    ):
        for name, history in await _histories(client):
            scrubbed = await decoded_and_scrubbed(history, payload_codec())
            path = out / f"{name.format(v=version)}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"{n.format(v=version)}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record_all(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
