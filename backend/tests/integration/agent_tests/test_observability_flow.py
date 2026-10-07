"""AC-20: one trace from the request through the retrieval workflow, its activities, the outbox,
the relay, the screening workflow, `screen` and `ai.call` (TASK-013 interface contract, "One
trace" and "API"; ADR-007, ADR-017, ADR-022).

The worker runs in this process (`build_workers`) behind a client with the tracing interceptor,
on a queue unique to this module. Spans come from the shared in-memory exporter; audit and outbox
rows are read back as the superuser. Expectations come from the contract.
"""

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import Worker

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.dispatch import queue_for
from abacus.kernel.db import configure_relay_engine
from abacus.kernel.telemetry import TRACEPARENT, current_trace_id, tracer
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow.relay import OutboxEvent, relay_once
from abacus.modules.agents.api import install_fake_responses
from abacus.modules.agents.screenings import (
    EVIDENCE_VERSION_CREATED,
    start_screening,
)
from abacus.modules.agents.screenings import (
    workflow_id as screening_workflow_id,
)
from abacus.modules.connections.api import (
    RetrievalInput,
    RetrievalOutcome,
    StartedRun,
    start_retrieval,
)
from abacus.modules.connections.api import (
    workflow_id as retrieval_workflow_id,
)
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus.worker.__main__ import build_workers
from abacus_tools.fakes.identity import FakeIdentityProvider

from . import tracing_support
from .support import PERIOD, Migrated, Seeder, World

QUEUE = f"obs-flow-{uuid.uuid4().hex[:12]}"
FORGED = "ef" * 16
RETRIEVAL_EVENTS = 9  # the audit events of one retrieval (see test_retrieval_workflow)


# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def task_queue(monkeypatch: pytest.MonkeyPatch, fake_dir: object) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    yield
    settings.cache_clear()


@pytest.fixture(autouse=True)
def relay_engine_for_this_loop(migrated_db: Migrated) -> None:
    configure_relay_engine(migrated_db.relay_url)


@pytest.fixture(autouse=True)
def exporter() -> Iterator[InMemorySpanExporter]:
    memory = tracing_support.install()
    memory.clear()
    yield memory
    memory.clear()


@asynccontextmanager
async def _serving() -> AsyncIterator[list[Worker]]:
    """Every class's pool (and the legacy queue), as `python -m abacus.worker` runs them."""
    async with AsyncExitStack() as pools:
        built = await build_workers()
        for pool in built:
            await pools.enter_async_context(pool)
        yield built


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    """A client WITH the tracing interceptor (the worker and the relay inherit it)."""
    client = await Client.connect(
        temporal_target, data_converter=data_converter(), interceptors=[TracingInterceptor()]
    )
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)


@pytest.fixture
async def worker(temporal: Client) -> AsyncIterator[list[Worker]]:
    async with _serving() as built:
        configure_provider(install_fake_responses(FakeModel()))
        yield built
    configure_provider(None)


# --- the flow ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Flow:
    trace_id: str
    run_id: uuid.UUID
    outcome: RetrievalOutcome
    version_id: uuid.UUID
    spans: list[ReadableSpan]


class OnlyThisTenant:
    """The screening subscription for one tenant (the shared database may hold other tests'
    unpublished events, which this publisher leaves alone)."""

    def __init__(self, tenant_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id

    async def publish(self, event: OutboxEvent) -> None:
        if event.tenant_id == self.tenant_id and event.event_type == EVIDENCE_VERSION_CREATED:
            await start_screening(event)


def _names(spans: list[ReadableSpan], prefix: str) -> list[str]:
    return [s.name for s in spans if s.name.startswith(prefix)]


async def _flow(temporal: Client, world: World) -> Flow:
    """Start a retrieval under one parent span, run it, relay its event, run the screening."""
    with tracer("test").start_as_current_span("test.parent"):
        trace_id = current_trace_id()
        assert trace_id is not None
        started = await start_retrieval(
            world.requester.context(),
            engagement_id=world.engagement_id,
            request_item_id=world.item_id,
            period=PERIOD,
        )
        assert isinstance(started, StartedRun)
        outcome: RetrievalOutcome = await temporal.execute_workflow(
            "retrieval",
            RetrievalInput(str(world.tenant_id), str(started.run_id)),
            id=retrieval_workflow_id(started.run_id),
            task_queue=queue_for("interactive"),
            execution_timeout=timedelta(seconds=90),
            result_type=RetrievalOutcome,
        )
    assert outcome.status == "succeeded"
    assert outcome.evidence_version_id is not None
    version_id = uuid.UUID(outcome.evidence_version_id)
    await relay_once(OnlyThisTenant(world.tenant_id), batch=500)
    await temporal.get_workflow_handle(screening_workflow_id(world.tenant_id, version_id)).result()
    spans = await tracing_support.until_spans(
        trace_id,
        lambda found: (
            any(s.name.startswith("RunWorkflow:") and "screening" in s.name for s in found)
            and any(s.name == "ai.call" for s in found)
        ),
    )
    return Flow(trace_id, started.run_id, outcome, version_id, spans)


# --- one trace -----------------------------------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac20_the_retrieval_workflow_and_every_activity_join_the_parents_trace(
    world: World, temporal: Client, exporter: InMemorySpanExporter
) -> None:
    flow = await _flow(temporal, world)
    names = [s.name for s in flow.spans]
    assert any(n.startswith("StartWorkflow:") and "retrieval" in n for n in names)
    assert any(n.startswith("RunWorkflow:") and "retrieval" in n for n in names)
    starts = _names(flow.spans, "StartActivity:")
    runs = _names(flow.spans, "RunActivity:")
    assert starts
    assert runs
    assert sorted(n.removeprefix("StartActivity:") for n in starts) == sorted(
        n.removeprefix("RunActivity:") for n in runs
    )
    # Nothing Temporal did for this flow fell outside the trace.
    stray = [
        s.name
        for s in exporter.get_finished_spans()
        if tracing_support.trace_hex(s) != flow.trace_id
        and s.name.startswith(("StartWorkflow", "RunWorkflow", "StartActivity", "RunActivity"))
    ]
    assert stray == []


@pytest.mark.usefixtures("worker")
async def test_ac20_every_audit_row_of_the_flow_carries_the_trace_id(
    seed: Seeder, world: World, temporal: Client
) -> None:
    flow = await _flow(temporal, world)
    rows = await seed.rows(
        "SELECT action, trace_id FROM audit_events WHERE tenant_id = $1 ORDER BY seq",
        world.tenant_id,
    )
    assert len(rows) >= RETRIEVAL_EVENTS + 1  # the retrieval's, then the screening's
    assert {r["trace_id"] for r in rows} == {flow.trace_id}
    actions = [str(r["action"]) for r in rows]
    assert "evidence_version.created" in actions
    assert "model.called" in actions  # written by the screening, in the same trace


@pytest.mark.usefixtures("worker")
async def test_ac20_the_outbox_row_carries_a_traceparent_of_the_same_trace(
    seed: Seeder, world: World, temporal: Client
) -> None:
    flow = await _flow(temporal, world)
    [row] = await seed.rows(
        "SELECT trace_context FROM outbox WHERE tenant_id = $1 AND event_type = $2",
        world.tenant_id,
        EVIDENCE_VERSION_CREATED,
    )
    stored = str(row["trace_context"])
    assert TRACEPARENT.fullmatch(stored)
    assert stored.split("-")[1] == flow.trace_id
    # ... and the span it names is one of this trace's.
    assert stored.split("-")[2] in {tracing_support.span_hex(s) for s in flow.spans}


@pytest.mark.usefixtures("worker")
async def test_ac20_the_relay_continues_the_trace_into_the_screening_workflow(
    world: World, temporal: Client
) -> None:
    flow = await _flow(temporal, world)
    names = [s.name for s in flow.spans]
    assert any(n.startswith("RunWorkflow:") and "screening" in n for n in names)
    [publish] = [s for s in flow.spans if s.name == "outbox.publish"]
    assert (publish.attributes or {})["outbox.event_type"] == EVIDENCE_VERSION_CREATED
    assert (publish.attributes or {})["tenant.id"] == str(world.tenant_id)
    ids = {tracing_support.span_hex(s) for s in flow.spans}
    assert publish.parent is not None
    assert format(publish.parent.span_id, "016x") in ids
    assert any(n.startswith("StartWorkflow:") and "screening" in n for n in names)


@pytest.mark.usefixtures("worker")
async def test_ac20_the_screening_activities_and_the_model_call_are_in_the_same_trace(
    world: World, temporal: Client
) -> None:
    flow = await _flow(temporal, world)
    runs = _names(flow.spans, "RunActivity:")
    assert any("screen" in n for n in runs), runs
    [ai] = [s for s in flow.spans if s.name == "ai.call"]
    attributes = dict(ai.attributes or {})
    assert str(attributes["ai.prompt"]).startswith("evidence.screen@")
    assert ai.parent is not None
    # ai.call hangs under the screen activity's span, itself under the screening workflow's.
    by_id = {tracing_support.span_hex(s): s for s in flow.spans}
    parent = by_id[format(ai.parent.span_id, "016x")]
    assert parent.name.startswith("RunActivity:")


@pytest.mark.usefixtures("worker")
async def test_ac20_the_flows_spans_hold_no_text_from_the_evidence(
    world: World, temporal: Client
) -> None:
    flow = await _flow(temporal, world)
    text = tracing_support.everything(flow.spans)
    assert "Seeded entity" not in text
    for span in flow.spans:
        assert [e for e in span.events if e.name == "exception"] == []


# --- the API -------------------------------------------------------------------------------------


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


async def _post(
    seed: Seeder,
    idp: FakeIdentityProvider,
    world: World,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    subject = str(
        await seed.value("SELECT idp_subject FROM users WHERE id = $1", world.requester.user_id)
    )
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            f"/v1/engagements/{world.engagement_id}/retrievals",
            json={
                "request_item_id": str(world.item_id),
                "period_start": PERIOD.start.isoformat(),
                "period_end": PERIOD.end.isoformat(),
            },
            headers={"Authorization": f"Bearer {idp.token(subject)}", **(headers or {})},
        )


@pytest.mark.usefixtures("worker")
async def test_ac20_an_api_request_the_workflow_and_the_audit_rows_share_one_trace(
    seed: Seeder,
    world: World,
    temporal: Client,
    idp: FakeIdentityProvider,
    exporter: InMemorySpanExporter,
) -> None:
    response = await _post(seed, idp, world)
    assert response.status_code == 202
    run_id = uuid.UUID(response.json()["sync_run_id"])
    await temporal.get_workflow_handle(retrieval_workflow_id(run_id)).result()
    [server] = [
        s
        for s in exporter.get_finished_spans()
        if s.parent is None and s.name == "POST /v1/engagements/{engagement_id}/retrievals"
    ]
    trace_id = tracing_support.trace_hex(server)
    spans = await tracing_support.until_spans(
        trace_id, lambda found: any(s.name.startswith("RunWorkflow:") for s in found)
    )
    names = [s.name for s in spans]
    assert any(n.startswith("StartWorkflow:") and "retrieval" in n for n in names)
    assert any(n.startswith("RunWorkflow:") and "retrieval" in n for n in names)
    assert any(n.startswith("RunActivity:") for n in names)
    rows = await seed.rows(
        "SELECT trace_id FROM audit_events WHERE tenant_id = $1", world.tenant_id
    )
    assert len(rows) >= RETRIEVAL_EVENTS
    assert {r["trace_id"] for r in rows} == {trace_id}


@pytest.mark.usefixtures("worker")
async def test_ac20_a_callers_traceparent_does_not_reach_the_audit_rows(
    seed: Seeder,
    world: World,
    temporal: Client,
    idp: FakeIdentityProvider,
) -> None:
    response = await _post(seed, idp, world, {"traceparent": f"00-{FORGED}-{'12' * 8}-01"})
    assert response.status_code == 202
    run_id = uuid.UUID(response.json()["sync_run_id"])
    await temporal.get_workflow_handle(retrieval_workflow_id(run_id)).result()
    rows = await seed.rows(
        "SELECT trace_id FROM audit_events WHERE tenant_id = $1", world.tenant_id
    )
    assert rows
    assert FORGED not in {r["trace_id"] for r in rows}
    assert None not in {r["trace_id"] for r in rows}


async def test_ac20_the_authorization_value_is_in_no_span_of_an_authenticated_call(
    seed: Seeder,
    world: World,
    idp: FakeIdentityProvider,
    exporter: InMemorySpanExporter,
) -> None:
    subject = str(
        await seed.value("SELECT idp_subject FROM users WHERE id = $1", world.requester.user_id)
    )
    token = idp.token(subject)
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    spans = list(exporter.get_finished_spans())
    [server] = [s for s in spans if s.parent is None]
    assert server.name == "GET /v1/me"
    assert token not in tracing_support.everything(spans)
    assert "Bearer" not in tracing_support.everything(spans)
