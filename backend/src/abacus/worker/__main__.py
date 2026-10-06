"""The workflow worker (ADR-017). PROTECTED. TASK-010 design §6.

Run: python -m abacus.worker

Fails at boot, not at first use, if the key service, evidence storage or payload codec isn't
usable: an AWS environment without its KMS key service never starts (ADR-104). The fake
connector's fixture directory must be shared with the API locally (`fake_connector_dir`).
"""

from __future__ import annotations

import asyncio
import sys

from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.crypto import key_service
from abacus.kernel.temporal import payload_codec, temporal_client
from abacus.modules.connections.api import ACTIVITIES, RetrievalWorkflow
from abacus.modules.evidence.api import check_ready


async def build_worker() -> Worker:
    key_service()
    payload_codec()
    await check_ready()
    client = await temporal_client()
    return Worker(
        client,
        task_queue=settings().temporal_task_queue,
        workflows=[RetrievalWorkflow],
        activities=list(ACTIVITIES),
    )


async def run() -> None:
    worker = await build_worker()
    await worker.run()


def main() -> int:
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
