"""Record the legal-hold workflows' replay histories (Q-02-T29; ADR-090). See `histories.py` for
the fixture rules.

Run: python -m abacus_tools.workflows.record_legal_holds <output-directory> [version]

Records one run of each real workflow against throwaway containers, with their activities replaced
by stubs (replay never runs activities). Each loops twice, so the batch loop is in the history:
- `legal-hold-apply-<version>-active.json`: two `apply_batch` steps, then `activate`;
- `legal-hold-release-<version>-released.json`: two `release_batch` steps, then
  `finish_release`.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import LegalHoldApply, LegalHoldInput, LegalHoldRelease
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_HOLD = "00000000-0000-4000-8000-0000000000a1"
_NAMES = ("legal-hold-apply-{v}-active.json", "legal-hold-release-{v}-released.json")
_left = {"apply": 1, "release": 1}


def _step(kind: str) -> int:
    pending, _left[kind] = _left[kind], 0
    return pending


@activity.defn(name="legal_hold.apply_batch")
async def _apply(given: LegalHoldInput) -> int:
    return _step("apply")


@activity.defn(name="legal_hold.activate")
async def _activate(given: LegalHoldInput) -> str:
    return "active"


@activity.defn(name="legal_hold.release_batch")
async def _release(given: LegalHoldInput) -> int:
    return _step("release")


@activity.defn(name="legal_hold.finish_release")
async def _finish(given: LegalHoldInput) -> str:
    return "released"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[LegalHoldApply, LegalHoldRelease],
        activities=[_apply, _activate, _release, _finish],
    ):
        for workflow, name in ((LegalHoldApply, _NAMES[0]), (LegalHoldRelease, _NAMES[1])):
            handle = await client.start_workflow(
                workflow.run,
                LegalHoldInput(_TENANT, _HOLD),
                id=f"recorder-{name.split('-{v}')[0]}-{version}",
                task_queue=_TASK_QUEUE,
            )
            await handle.result()
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            path = out / name.format(v=version)
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [n.format(v=version) for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
