"""Record screening replay histories (AC-19, ADR-090). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_screening <output-directory> [version]

Retrieves one synthetic trial balance, then records three runs of the real screening workflow
against throwaway containers, with the fake model:
- `screening-<version>-completed.json`: the fake screener answers;
- `screening-<version>-skipped.json`: no `requested_by`, so no run is created;
- `screening-<version>-provider-unavailable.json`: no fake answer, so the model call fails until
  retries run out and `screening.fail_run` ends the run.

Refuses to overwrite an existing file: a changed workflow records `v<N+1>`.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.kernel.temporal import payload_codec
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections
from abacus_tools.synthetic.connector_fixtures import write_trial_balance
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import (
    Stack,
    connect,
    period_of,
    refuse_overwrite,
    run_with_stack,
    seed,
    trial_balance,
)

_TASK_QUEUE = "abacus-recorder"
_NAMES = ("completed", "skipped", "provider-unavailable")


async def _screen(
    client: Client, name: str, input: agents.ScreeningInput, model: FakeModel
) -> WorkflowHistory:
    configure_provider(model)
    try:
        handle = await client.start_workflow(
            "screening", input, id=f"recorder-screening-{name}", task_queue=_TASK_QUEUE
        )
        await handle.result()
        return await handle.fetch_history()
    finally:
        configure_provider(None)


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    world = await seed(stack.superuser)
    tb = trial_balance()
    period = period_of(tb)
    write_trial_balance(
        Path(os.environ["ABACUS_FAKE_CONNECTOR_DIR"]),
        world.connection,
        tb,
        period_start=period.start,
        entity_name="Example",
    )
    codec = payload_codec()
    worker = Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[*connections.WORKFLOWS, *agents.WORKFLOWS],
        activities=[*connections.ACTIVITIES, *agents.ACTIVITIES],
    )
    async with worker:
        started = await connections.start_retrieval(
            world.context(),
            engagement_id=world.engagement,
            request_item_id=world.items[0],
            period=period,
        )
        retrieval = await client.start_workflow(
            "retrieval",
            connections.RetrievalInput(str(world.tenant), str(started.run_id)),
            id=connections.workflow_id(started.run_id),
            task_queue=_TASK_QUEUE,
            result_type=connections.RetrievalOutcome,
        )
        outcome = await retrieval.result()
        version_id = str(outcome.evidence_version_id)
        cases = (
            ("completed", str(world.user), agents.install_fake_responses(FakeModel())),
            ("skipped", None, FakeModel()),
            ("provider-unavailable", str(world.user), FakeModel()),
        )
        for name, requested_by, model in cases:
            input = agents.ScreeningInput(
                str(world.tenant), version_id, str(uuid.uuid4()), requested_by
            )
            history = await _screen(client, name, input, model)
            scrubbed = await decoded_and_scrubbed(history, codec)
            path = out / f"screening-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"screening-{version}-{name}.json" for name in _NAMES]):
        return 1
    out.mkdir(parents=True, exist_ok=True)
    run_with_stack(lambda stack: _record(out, version, stack))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
