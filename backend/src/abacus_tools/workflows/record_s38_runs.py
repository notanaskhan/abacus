"""Record S38's new workflow's replay histories (T-04-T38; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_s38_runs <output-directory>

Activities are stubbed (no database), so each history pins the command sequence only:

- `analyst-mode-v1-proposed.json`: the run set running, one mode activity that proposed, then
  succeeded.
- `analyst-mode-v1-refused.json`: the mode activity refused (no consent), then the run failed.

A history on disk is never overwritten.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Final

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.tax.api import (
    AnalystModeWorkflow,
    ModeRunInput,
    ModeRunOutcome,
    mode_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TENANT: Final = "00000000-0000-4000-8000-0000000000aa"
_ENTITY: Final = "00000000-0000-4000-8000-0000000000e1"
_RETURN: Final = "00000000-0000-4000-8000-0000000000f1"
_QUEUE: Final = "record-s38"
_PROPOSAL: Final = "00000000-0000-4000-8000-0000000000d1"


class _Stubs:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def activities(self) -> list[Any]:  # Any: activity callables
        @activity.defn(name="agents.run_v2.set_state")
        async def set_state(
            tenant_id: str, run_id: str, state: str, reason: str | None, extra: object
        ) -> int:
            return 1

        @activity.defn(name="tax.analyst_mode.run")
        async def mode(p: ModeRunInput) -> ModeRunOutcome:
            if self.scenario == "refused":
                return ModeRunOutcome("refused", code="consent_required")
            return ModeRunOutcome("proposed", _PROPOSAL, 7)

        return [set_state, mode]


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    for n, scenario in enumerate(("proposed", "refused"), start=1):
        name = f"analyst-mode-v1-{scenario}.json"
        if (out / name).exists():
            print(f"{name} is recorded; skipped")
            continue
        queue = f"{_QUEUE}-{n}"
        run_id = f"00000000-0000-4000-8000-{n:012d}"
        async with Worker(
            client,
            task_queue=queue,
            workflows=[AnalystModeWorkflow],
            activities=_Stubs(scenario).activities(),
        ):
            handle = await client.start_workflow(
                AnalystModeWorkflow.run,
                ModeRunInput(_TENANT, run_id, "k1_treatments", _ENTITY, 2025, _RETURN),
                id=mode_workflow_id(_TENANT, run_id),
                task_queue=queue,
            )
            await asyncio.wait_for(handle.result(), timeout=180)
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            (out / name).write_text(scrubbed.to_json())
            print(f"recorded {out / name}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
