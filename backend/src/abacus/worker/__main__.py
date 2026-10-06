"""The workflow worker (ADR-017). PROTECTED. TASK-010 design §6, revision 1.

Run: python -m abacus.worker

Fails at boot, not at first use, if the database (application and relay roles), key service,
evidence storage or payload codec isn't usable: an AWS environment without its KMS key service
never starts (ADR-104). Workflows and activities come from each module's registry (`WORKFLOWS`,
`ACTIVITIES` in its `api.py`), so adding one doesn't touch the worker. On SIGTERM it stops
polling and lets running activities finish (up to `GRACEFUL_SHUTDOWN`) before exiting. Locally
the fake connector's fixture directory must be shared with the API (`fake_connector_dir`).

It also runs the outbox relay (TASK-011 Q4): events go to the handlers modules subscribe in
their `SUBSCRIPTIONS` (e.g. `evidence_version.created` starts screening). The relay stops with
the worker; an event mid-publish is simply republished later (at least once). If the relay task
ever dies, the worker stops and exits non-zero, so it is restarted rather than running without
one. Accepted risk (Q4): the worker holds the relay role, which reads every firm's outbox.

Locally (`environment == "local"`) the model provider is the fake screener (TASK-011 Q3); there
is no real provider yet, so elsewhere screening ends as `internal_error` until one is set up.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from datetime import timedelta

from temporalio.worker import Worker

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.kernel.config import settings
from abacus.kernel.crypto import key_service
from abacus.kernel.db import ping, ping_relay
from abacus.kernel.temporal import payload_codec, temporal_client
from abacus.kernel.uow import Handler
from abacus.kernel.uow.relay import RoutingPublisher, run_relay
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections
from abacus.modules.evidence.api import check_ready

GRACEFUL_SHUTDOWN = timedelta(seconds=60)
MODULES = (connections, agents)
SUBSCRIBERS = tuple(module.SUBSCRIPTIONS for module in MODULES)


def publisher() -> RoutingPublisher:
    handlers: dict[str, list[Handler]] = {}
    for subscriptions in SUBSCRIBERS:
        for event_type, handler in subscriptions.items():
            handlers.setdefault(event_type, []).append(handler)
    return RoutingPublisher(handlers)


async def build_worker() -> Worker:
    await ping()
    await ping_relay()
    key_service()
    payload_codec()
    await check_ready()
    if settings().environment == "local":
        configure_provider(agents.install_fake_responses(FakeModel()))
    client = await temporal_client()
    return Worker(
        client,
        task_queue=settings().temporal_task_queue,
        workflows=[w for module in MODULES for w in module.WORKFLOWS],
        activities=[a for module in MODULES for a in module.ACTIVITIES],
        graceful_shutdown_timeout=GRACEFUL_SHUTDOWN,
    )


async def run() -> None:
    worker = await build_worker()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    async with worker:
        relay = asyncio.create_task(run_relay(publisher(), stop))
        relay.add_done_callback(lambda _: stop.set())  # a dead relay stops the worker
        try:
            await stop.wait()
        finally:
            stop.set()
            await relay


def main() -> int:
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
