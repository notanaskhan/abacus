"""Record the withdrawal purge's replay history (P-06-T19; ADR-162 §7; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_withdrawal_purge <output-directory> [version]

Records one run of the real workflow against throwaway containers, with its activity replaced by
a stub (replay never runs activities): the window's timer (a second here, from the input), an
erase attempt that is blocked (it answers one second to wait, standing in for a day), the retry
timer, then the attempt that erases (0):
- `withdrawal-purge-<version>-blocked-then-erased.json`.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import EvidenceWithdrawalPurge, WithdrawalPurgeInput
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_VERSION = "00000000-0000-4000-8000-0000000000b1"
_NAME = "withdrawal-purge-{v}-blocked-then-erased.json"
_answers = [1, 0]


@activity.defn(name="evidence_withdrawal.erase")
async def _erase(given: WithdrawalPurgeInput) -> int:
    return _answers.pop(0)


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[EvidenceWithdrawalPurge],
        activities=[_erase],
    ):
        handle = await client.start_workflow(
            EvidenceWithdrawalPurge.run,
            WithdrawalPurgeInput(_TENANT, _VERSION, 1),
            id=f"recorder-withdrawal-purge-{version}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        path = out / _NAME.format(v=version)
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [_NAME.format(v=version)]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
