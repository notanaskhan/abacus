"""Record S36's new workflows' replay histories (P-10-T38, T-04-T31; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_s36_runs <output-directory>

Activities are stubbed (no database), so each history pins the command sequence only:

- `approved-write-v1-saved.json`: the Undo window's timer, then one execute activity.
- `fix-run-v1-proposed.json`: the run set running, the fix proposes, the run succeeds.
- `fix-run-v1-consent-waited.json`: the fix answers `waiting_on_inputs`; the run waits until
  `inputs_ready`, then fixes again and succeeds.
- `issue-explain-v1-explained.json`: the run set running, one explanation, the run succeeds.

A history on disk is never overwritten.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Final

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import ApprovedWriteInput, ApprovedWriteWorkflow, approved_write_id
from abacus.modules.tax.api import (
    ExplainRunInput,
    ExplainRunOutcome,
    FixRunInput,
    FixRunOutcome,
    FixRunWorkflow,
    IssueExplainWorkflow,
    explain_workflow_id,
    fix_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_QUEUE: Final = "abacus-recorder-s36"
_TENANT: Final = "00000000-0000-4000-8000-0000000000b1"
_ISSUE: Final = "00000000-0000-4000-8000-0000000018a1"
_ENTITY: Final = "00000000-0000-4000-8000-00000000fe1d"
_PROPOSAL: Final = "00000000-0000-4000-8000-00000000a0a1"


class _Stubs:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.calls = 0

    def activities(self) -> list[Callable[..., Awaitable[object]]]:
        stubs = self

        @activity.defn(name="agents.run_v2.set_state")
        async def set_state(
            tenant_id: str,
            run_id: str,
            state: str,
            reason: str | None,
            blocked: dict[str, Any] | None,  # Any: JSON (Temporal cannot decode `object`)
        ) -> int:
            return 1

        @activity.defn(name="tax.fix_runner.fix")
        async def fix(p: FixRunInput) -> FixRunOutcome:
            stubs.calls += 1
            if stubs.scenario == "consent-waited" and stubs.calls == 1:
                return FixRunOutcome("waiting_on_inputs", ["consent_7216"])
            return FixRunOutcome("proposed", [], _PROPOSAL, 2)

        @activity.defn(name="tax.explain.explain")
        async def explain(p: ExplainRunInput) -> ExplainRunOutcome:
            return ExplainRunOutcome("explained", [], "00000000-0000-4000-8000-00000000e0e1", 1)

        @activity.defn(name="agents.approved_write.execute")
        async def execute(p: ApprovedWriteInput) -> str:
            return "saved"

        return [set_state, fix, explain, execute]


def _run_id(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


async def _save(client: Client, out: Path, name: str, handle: Any) -> None:  # noqa: ANN401 -- a handle of any workflow class
    await asyncio.wait_for(handle.result(), timeout=180)  # a stuck run fails, not hangs
    scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    (out / name).write_text(scrubbed.to_json())
    print(f"recorded {out / name}")


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    plan: list[tuple[str, str]] = [
        ("approved-write-v1-saved.json", "saved"),
        ("fix-run-v1-proposed.json", "proposed"),
        ("fix-run-v1-consent-waited.json", "consent-waited"),
        ("issue-explain-v1-explained.json", "explained"),
    ]
    for n, (name, scenario) in enumerate(plan, start=1):
        if (out / name).exists():
            print(f"{name} is recorded; skipped")
            continue
        stubs = _Stubs(scenario)
        queue = f"{_QUEUE}-{n}"
        workflows = [ApprovedWriteWorkflow, FixRunWorkflow, IssueExplainWorkflow]
        async with Worker(
            client, task_queue=queue, workflows=workflows, activities=stubs.activities()
        ):
            run = _run_id(n)
            if scenario == "saved":
                grant = _run_id(100 + n)
                handle = await client.start_workflow(
                    ApprovedWriteWorkflow.run,
                    ApprovedWriteInput(_TENANT, run, _PROPOSAL, grant, "files.save_approved"),
                    id=approved_write_id(_TENANT, grant),
                    task_queue=queue,
                )
            elif scenario == "explained":
                handle = await client.start_workflow(
                    IssueExplainWorkflow.run,
                    ExplainRunInput(_TENANT, run, _ISSUE, _ENTITY, 2025),
                    id=explain_workflow_id(_TENANT, run),
                    task_queue=queue,
                )
            else:
                handle = await client.start_workflow(
                    FixRunWorkflow.run,
                    FixRunInput(_TENANT, run, _ISSUE, _ENTITY, 2025),
                    id=fix_workflow_id(_TENANT, run),
                    task_queue=queue,
                )
                if scenario == "consent-waited":
                    await asyncio.sleep(2)
                    await handle.signal("inputs_ready")
            await _save(client, out, name, handle)


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
