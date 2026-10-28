"""Record the sender domain verification's replay history (R-01-T27; DEC-954; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_sending_domain <output-directory> [version]

Records one run of the real `SendingDomainVerification` against throwaway containers, with its
activity replaced by a stub (replay never runs activities): the first check answers `verified`,
so the run ends without its 15-minute timer:
- `sending-domain-<version>-verified.json`.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.communications.workflows import (
    SendingDomainVerificationInput,
    SendingDomainVerificationWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_DOMAIN = "00000000-0000-4000-8000-0000000000d1"
_NAME = "sending-domain-{v}-verified.json"


@activity.defn(name="communications.check_sending_domain")
async def _check(given: SendingDomainVerificationInput) -> str:
    return "verified"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[SendingDomainVerificationWorkflow],
        activities=[_check],
    ):
        handle = await client.start_workflow(
            SendingDomainVerificationWorkflow.run,
            SendingDomainVerificationInput(_TENANT, _DOMAIN),
            id=f"recorder-sending-domain-{version}",
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
