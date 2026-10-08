"""The workflow worker (ADR-017). PROTECTED. TASK-010 design §6, revision 1.

Run: python -m abacus.worker [--classes interactive,time_sensitive,background,batch]

One worker pool per work class served (ADR-071, SPEC-003), each polling `<base>-<class>` with its
own concurrency limits; by default a process serves all four. The process serving the interactive
pool also runs the outbox relay and, for one release, drains the legacy single queue
(`serve_legacy_queue`).

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

import argparse
import asyncio
import signal
import sys
from collections.abc import Sequence
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from abacus.ai_gateway import FakeModel, check_provider_limits, configure_provider
from abacus.ai_gateway.budgets import run_anomaly_job
from abacus.kernel.config import settings
from abacus.kernel.crypto import key_service
from abacus.kernel.db import ping, ping_relay
from abacus.kernel.dispatch import WORK_CLASSES, WorkClass, queue_for
from abacus.kernel.error_tracking import (
    ReportingInterceptor,
    configure_error_tracking,
    flush_errors,
)
from abacus.kernel.metrics import configure_metrics, shutdown_metrics
from abacus.kernel.telemetry import configure_tracing, shutdown_tracing
from abacus.kernel.temporal import payload_codec, temporal_client
from abacus.kernel.temporal_metrics import ScheduleToStartInterceptor
from abacus.kernel.uow import Handler
from abacus.kernel.uow.relay import RoutingPublisher, run_relay
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections
from abacus.modules.evidence.api import check_ready
from abacus.modules.notifications import api as notifications

GRACEFUL_SHUTDOWN = timedelta(seconds=60)
MODULES = (connections, agents, notifications)
SUBSCRIBERS = tuple(module.SUBSCRIPTIONS for module in MODULES)


def publisher() -> RoutingPublisher:
    handlers: dict[str, list[Handler]] = {}
    for subscriptions in SUBSCRIBERS:
        for event_type, handler in subscriptions.items():
            handlers.setdefault(event_type, []).append(handler)
    return RoutingPublisher(handlers)


def _worker(client: Client, task_queue: str, work_class: WorkClass | None) -> Worker:
    """One pool: every module's workflows and activities, polling one task queue."""
    limits = settings().work_classes[work_class or "interactive"]  # legacy: interactive limits
    return Worker(
        client,
        task_queue=task_queue,
        workflows=[w for module in MODULES for w in module.WORKFLOWS],
        activities=[a for module in MODULES for a in module.ACTIVITIES],
        max_concurrent_activities=limits.max_activities,
        max_concurrent_workflow_tasks=limits.max_workflow_tasks,
        # Tracing comes with the client (kernel.temporal); error reporting and the
        # schedule-to-start metric are the worker's.
        interceptors=[ReportingInterceptor(), ScheduleToStartInterceptor()],
        graceful_shutdown_timeout=GRACEFUL_SHUTDOWN,
    )


async def build_workers(classes: Sequence[WorkClass] = WORK_CLASSES) -> list[Worker]:
    """One pool per work class served (ADR-071), plus the legacy single queue while workflows
    started before the class queues may still be open on it (SPEC-003 AC-16)."""
    configure_tracing("abacus-worker")
    configure_metrics("abacus-worker")
    configure_error_tracking("abacus-worker")
    await ping()
    await ping_relay()
    key_service()
    payload_codec()
    await check_ready()
    check_provider_limits()
    if settings().environment == "local":
        configure_provider(agents.install_fake_responses(FakeModel()))
    client = await temporal_client()
    workers = [_worker(client, queue_for(c), c) for c in classes]
    # The legacy queue (any class's work) drains only beside the interactive pool, so a batch-only
    # process never runs interactive work.
    if settings().serve_legacy_queue and "interactive" in classes:
        workers.append(_worker(client, settings().temporal_task_queue, None))
    return workers


def classes_from(argv: Sequence[str]) -> tuple[WorkClass, ...]:
    """`--classes interactive,time_sensitive` (default: all four)."""
    parser = argparse.ArgumentParser(prog="python -m abacus.worker")
    parser.add_argument("--classes", default=",".join(WORK_CLASSES))
    raw = parser.parse_args(list(argv)).classes
    chosen = tuple(dict.fromkeys(c.strip() for c in raw.split(",") if c.strip()))
    unknown = [c for c in chosen if c not in WORK_CLASSES]
    if unknown or not chosen:
        parser.error(f"--classes takes some of {', '.join(WORK_CLASSES)}")
    return tuple(c for c in WORK_CLASSES if c in chosen)


async def run(classes: Sequence[WorkClass] = WORK_CLASSES) -> None:
    """Run every pool (and, beside the interactive pool, the relay) until a signal, or until any
    of them stops: one pool or the relay dying stops the process, which exits non-zero."""
    workers = await build_workers(classes)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    pools = [asyncio.create_task(worker.run()) for worker in workers]
    # The relay (and its role, which reads every firm's outbox) runs only in the process that
    # serves the interactive pool, so splitting classes doesn't multiply it.
    relay = run_relay(publisher(), stop) if "interactive" in classes else None
    # The spend-anomaly job (SPEC-007 AC-6) runs hourly beside the relay, once per deployment.
    anomaly = run_anomaly_job(stop) if "interactive" in classes else None
    # SPEC-013 AC-10: the daily notification purge, once per deployment like the relay.
    purge = notifications.run_purge_job(stop) if "interactive" in classes else None
    side = [job for job in (relay, anomaly, purge) if job is not None]
    tasks = [*pools, *(asyncio.create_task(job) for job in side)]
    stopped = asyncio.create_task(stop.wait())
    early: list[asyncio.Task[None]] = []
    try:
        await asyncio.wait([*tasks, stopped], return_when=asyncio.FIRST_COMPLETED)
        # Anything that ended before the signal ended unexpectedly, even without an error.
        early = [task for task in tasks if task.done()] if not stop.is_set() else []
    finally:
        stop.set()
        # Every pool stops polling at once, then drains (up to GRACEFUL_SHUTDOWN each, together).
        await asyncio.gather(*(worker.shutdown() for worker in workers), return_exceptions=True)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        stopped.cancel()
        # Only after the drain: spans, metrics and errors of the last activities are exported.
        shutdown_tracing()
        shutdown_metrics()
        flush_errors()
    failures = [r for r in results if isinstance(r, BaseException)]
    if failures:
        raise failures[0]
    if early:
        raise RuntimeError("a worker pool or the relay stopped before the signal")


def main(argv: Sequence[str] | None = None) -> int:
    classes = classes_from(sys.argv[1:] if argv is None else argv)
    asyncio.run(run(classes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
