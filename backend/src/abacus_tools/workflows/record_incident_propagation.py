"""Record `IncidentPropagation`'s replay history (Q-02-T33; ADR-090). See `histories.py` for the
fixture rules.

Run: python -m abacus_tools.workflows.record_incident_propagation <output-directory> [version]

Records one run of the real workflow against throwaway containers, with its activities replaced
by stubs (replay never runs activities). Synthetic identifiers and facts only. Refuses to
overwrite an existing file.
- v1 (recorded before `incident_isolated_v2`): `incident-propagation-v1-three-firms.json`, one
  `platform.propagate_incident` step per firm for three firms. Not re-recordable from today's
  code, which takes the v2 branch.
- v2: `incident-propagation-v2-one-firm-fails.json`, four firms in one batch, the second failing
  non-retryably, then `platform.finish_incident_propagation` naming it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.platform.api import (
    IncidentFactsInput,
    IncidentPropagationInput,
    IncidentPropagationOutcome,
    IncidentPropagationStep,
    IncidentPropagationWorkflow,
    IncidentStepResult,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANTS = tuple(f"00000000-0000-4000-8000-00000000000{n}" for n in (1, 2, 3, 4))
_STAFF = "00000000-0000-4000-8000-0000000000f1"
_NAMES = {
    "v1": "incident-propagation-v1-three-firms.json",
    "v2": "incident-propagation-v2-one-firm-fails.json",
}
_FACTS = IncidentFactsInput(
    title="Synthetic sub-processor incident",
    event_kind="vendor_incident",
    discovered_at="2026-09-10T14:05:00+00:00",
    consumers_affected=0,
    unencrypted=False,
    confirmed_at="2026-09-11T09:00:00+00:00",
)


@activity.defn(name="platform.propagate_incident")
async def _propagate(step: IncidentPropagationStep) -> str:
    return "INC-2026-001"


@activity.defn(name="platform.propagate_incident_v2")
async def _propagate_v2(step: IncidentPropagationStep) -> IncidentStepResult:
    if step.tenant_id == _TENANTS[1]:
        raise ApplicationError("OperationalError", type="OperationalError", non_retryable=True)
    return IncidentStepResult(step.tenant_id, "INC-2026-001", "written")


@activity.defn(name="platform.finish_incident_propagation")
async def _finish(outcome: IncidentPropagationOutcome) -> None:
    return None


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[IncidentPropagationWorkflow],
        activities=[_propagate, _propagate_v2, _finish],
    ):
        firms = _TENANTS[:3] if version == "v1" else _TENANTS
        handle = await client.start_workflow(
            IncidentPropagationWorkflow.run,
            IncidentPropagationInput("ACC-2026-001", firms, _FACTS, _STAFF, "0" * 64),
            id=f"recorder-incident-propagation-{version}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        path = out / _NAMES[version]
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v2"
    if version not in _NAMES:
        print(f"unknown version {version!r}; one of {', '.join(_NAMES)}")
        return 2
    if refuse_overwrite(out, [_NAMES[version]]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
