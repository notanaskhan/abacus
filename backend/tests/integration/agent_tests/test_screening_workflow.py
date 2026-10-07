"""AC-14, AC-15, AC-16, AC-17, AC-19: the `screening` workflow against a local Temporal with the
real worker (TASK-011b interface contract: "Subscription" and "Workflow `screening`"; ADR-017).

The worker runs in this process (`build_workers`, so the registries, the boot order and the
workflow sandbox are all exercised) on a task queue unique to this module, and the client uses
the platform payload codec. The model is a `FakeModel` or a scripted provider. A retrieved trial
balance comes from the real pipeline; its `evidence_version.created` event is read back from the
outbox. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import cast

import pytest
from temporalio.api.common.v1 import Payload
from temporalio.client import Client, WorkflowFailureError, WorkflowHandle
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError
from temporalio.worker import Worker

from abacus.ai_gateway import (
    FakeModel,
    ModelRequest,
    ModelResponse,
    ProviderError,
    configure_provider,
)
from abacus.kernel.config import settings
from abacus.kernel.crypto.payload_codec import ENCODING
from abacus.kernel.db import configure_relay_engine
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import configure_temporal_client, data_converter, payload_codec
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents import activities
from abacus.modules.agents.api import (
    SCREEN_PROMPT,
    ScreeningInput,
    ScreeningWorkflow,
    screening_responder,
    start_screening,
    workflow_id,
)
from abacus.modules.agents.screenings import EVIDENCE_VERSION_CREATED, screening_input
from abacus.modules.agents.workflow_types import ScreeningOutcome
from abacus.worker.__main__ import build_workers

from .support import ENTITY, TB, Migrated, Seeder, World, retrieve, uploaded_version

QUEUE = f"screening-wf-{uuid.uuid4().hex[:12]}"
INVALID = "this is not json at all, and it is long enough to carry some tokens " * 3
LEAKED = "leak-marker-from-a-failing-provider-98765"


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


@asynccontextmanager
async def _serving() -> AsyncGenerator[list[Worker]]:
    """Every class's pool (and the legacy queue), as `python -m abacus.worker` runs them."""
    async with AsyncExitStack() as pools:
        built = await build_workers()
        for pool in built:
            await pools.enter_async_context(pool)
        yield built


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)


@pytest.fixture
async def worker(temporal: Client) -> AsyncIterator[list[Worker]]:
    async with _serving() as built:
        yield built


class Model:
    """The configured provider: counts requests, answers through `reply` (default: stock)."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []
        self.reply: Callable[[ModelRequest], str] = screening_responder
        fake = FakeModel()
        fake.respond(SCREEN_PROMPT, self._respond)
        configure_provider(fake)

    def _respond(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return self.reply(request)


@pytest.fixture
def model() -> Iterator[Model]:
    yield Model()
    configure_provider(None)


class Gate:
    """A provider that holds each call until released, then answers like the stock fake."""

    def __init__(self) -> None:
        self.inner = FakeModel()
        self.inner.respond(SCREEN_PROMPT, screening_responder)
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return await self.inner.complete(request)


@pytest.fixture
def gate() -> Iterator[Gate]:
    held = Gate()
    configure_provider(held)
    yield held
    held.release.set()
    configure_provider(None)


# --- helpers -------------------------------------------------------------------------------------


async def _created_event(seed: Seeder, world: World) -> OutboxEvent:
    """The `evidence_version.created` event the retrieval wrote, as the relay would deliver it."""
    await retrieve(world)
    [row] = await seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox "
        "WHERE tenant_id = $1 AND event_type = $2",
        world.tenant_id,
        EVIDENCE_VERSION_CREATED,
    )
    payload = row["payload"]
    loaded = json.loads(payload) if isinstance(payload, str) else payload
    return OutboxEvent(row["id"], row["tenant_id"], str(row["event_type"]), loaded)


def _input(world: World, version_id: uuid.UUID, requested_by: uuid.UUID | None) -> ScreeningInput:
    return ScreeningInput(
        str(world.tenant_id),
        str(version_id),
        str(uuid.uuid4()),
        str(requested_by) if requested_by else None,
    )


async def _execute(temporal: Client, given: ScreeningInput) -> ScreeningOutcome:
    return await temporal.execute_workflow(
        ScreeningWorkflow.run,
        given,
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("time_sensitive"),
        execution_timeout=timedelta(seconds=90),
    )


async def _start(
    temporal: Client, given: ScreeningInput
) -> WorkflowHandle[ScreeningWorkflow, ScreeningOutcome]:
    return await temporal.start_workflow(
        ScreeningWorkflow.run,
        given,
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("time_sensitive"),
        execution_timeout=timedelta(seconds=90),
    )


async def _row(seed: Seeder, run_id: str) -> tuple[str, str | None]:
    [row] = await seed.rows(
        "SELECT status, failure_code FROM agent_runs WHERE id = $1", uuid.UUID(run_id)
    )
    return str(row["status"]), cast("str | None", row["failure_code"])


def _handle(
    temporal: Client, workflow: str
) -> WorkflowHandle[ScreeningWorkflow, ScreeningOutcome]:
    return temporal.get_workflow_handle_for(ScreeningWorkflow.run, workflow)


async def _scheduled_activities(
    handle: WorkflowHandle[ScreeningWorkflow, ScreeningOutcome],
) -> list[str]:
    history = await handle.fetch_history()
    return [
        e.activity_task_scheduled_event_attributes.activity_type.name
        for e in history.events
        if e.HasField("activity_task_scheduled_event_attributes")
    ]


# --- AC-14: starting from the relayed event ------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac14_the_relayed_event_starts_one_screening_that_completes(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    assert event.payload["requested_by"] == str(world.requester.user_id)
    await start_screening(event)
    handle = _handle(
        temporal,
        workflow_id(event.tenant_id, uuid.UUID(str(event.payload["evidence_version_id"]))),
    )
    outcome = await handle.result()
    assert isinstance(outcome, ScreeningOutcome)
    assert outcome.status == "completed"
    assert outcome.screening_result_id is not None
    assert await seed.count("agent_runs", world.tenant_id) == 1
    assert await seed.count("screening_results", world.tenant_id) == 1
    assert await seed.count("usage_records", world.tenant_id) == 1
    [result] = await seed.rows(
        "SELECT created_by_kind FROM screening_results WHERE tenant_id = $1", world.tenant_id
    )
    assert result["created_by_kind"] == "agent"  # AC-14


@pytest.mark.usefixtures("worker")
async def test_ac14_the_workflow_is_started_with_the_tenant_qualified_id_and_queue_and_no_timeout(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    version_id = str(event.payload["evidence_version_id"])
    await start_screening(event)
    handle = _handle(temporal, f"screening:{world.tenant_id}:{version_id}")
    description = await handle.describe()
    assert description.id == f"screening:{world.tenant_id}:{version_id}"
    assert description.task_queue == queue_for("time_sensitive")
    history = await handle.fetch_history()
    started = history.events[0].workflow_execution_started_event_attributes
    assert started.workflow_execution_timeout.seconds == 0  # no execution timeout
    await handle.result()


@pytest.mark.usefixtures("worker")
async def test_ac14_a_redelivered_event_never_makes_a_second_run_or_result(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    version_id = uuid.UUID(str(event.payload["evidence_version_id"]))
    await start_screening(event)
    handle = _handle(temporal, workflow_id(event.tenant_id, version_id))
    first = await handle.result()
    first_run_id = (await handle.describe()).run_id
    # The finished workflow counts as delivered, whatever the redelivery looks like.
    await start_screening(event)
    await start_screening(event)
    redelivered = OutboxEvent(uuid.uuid4(), event.tenant_id, event.event_type, event.payload)
    await start_screening(redelivered)
    again = _handle(temporal, workflow_id(event.tenant_id, version_id))
    assert (await again.describe()).run_id == first_run_id
    assert await again.result() == first
    assert await seed.count("agent_runs", world.tenant_id) == 1
    assert await seed.count("screening_results", world.tenant_id) == 1
    assert await seed.count("usage_records", world.tenant_id) == 1
    assert len(model.requests) == 1


@pytest.mark.usefixtures("worker")
async def test_ac14_a_delivery_while_the_workflow_runs_attaches_to_it(
    seed: Seeder, world: World, temporal: Client, gate: Gate
) -> None:
    event = await _created_event(seed, world)
    version_id = uuid.UUID(str(event.payload["evidence_version_id"]))
    await start_screening(event)
    await asyncio.wait_for(gate.started.wait(), timeout=20)
    handle = _handle(temporal, workflow_id(event.tenant_id, version_id))
    running = (await handle.describe()).run_id
    await start_screening(event)  # no error, no second workflow
    assert (await handle.describe()).run_id == running
    gate.release.set()
    outcome = await handle.result()
    assert isinstance(outcome, ScreeningOutcome)
    assert outcome.status == "completed"
    assert gate.calls == 1
    assert await seed.count("agent_runs", world.tenant_id) == 1
    assert await seed.count("screening_results", world.tenant_id) == 1


@pytest.mark.usefixtures("worker")
async def test_ac14_a_failed_workflow_may_be_started_again_by_a_redelivery(
    world: World, temporal: Client, model: Model
) -> None:
    missing = uuid.uuid4()
    event = OutboxEvent(
        uuid.uuid4(),
        world.tenant_id,
        EVIDENCE_VERSION_CREATED,
        {"evidence_version_id": str(missing), "requested_by": str(world.requester.user_id)},
    )
    await start_screening(event)
    handle = _handle(temporal, workflow_id(world.tenant_id, missing))
    with pytest.raises(WorkflowFailureError):
        await handle.result()
    first = (await handle.describe()).run_id
    await start_screening(event)  # a failed run does not block the redelivery
    second_handle = _handle(temporal, workflow_id(world.tenant_id, missing))
    with pytest.raises(WorkflowFailureError):
        await second_handle.result()
    assert (await second_handle.describe()).run_id != first


# --- the workflow's paths ------------------------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac14_without_a_requester_the_workflow_is_skipped_after_one_activity(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    given = screening_input(
        OutboxEvent(
            event.event_id,
            event.tenant_id,
            event.event_type,
            {**event.payload, "requested_by": None},
        )
    )
    assert given.requested_by is None
    handle = await _start(temporal, given)
    assert await handle.result() == ScreeningOutcome("skipped")
    assert await _scheduled_activities(handle) == ["screening.create_run"]
    assert await seed.count("agent_runs", world.tenant_id) == 0
    assert model.requests == []


@pytest.mark.usefixtures("worker")
async def test_ac17_a_requester_without_an_active_membership_is_skipped(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    await seed.revoke(world.requester)
    handle = await _start(temporal, screening_input(event))
    assert await handle.result() == ScreeningOutcome("skipped")
    assert await _scheduled_activities(handle) == ["screening.create_run"]
    assert await seed.count("agent_runs", world.tenant_id) == 0
    assert model.requests == []


@pytest.mark.usefixtures("worker")
async def test_ac14_a_version_without_a_snapshot_is_skipped(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    version_id = await uploaded_version(seed, world)
    handle = await _start(temporal, _input(world, version_id, world.requester.user_id))
    assert await handle.result() == ScreeningOutcome("skipped")
    assert await _scheduled_activities(handle) == ["screening.create_run"]
    assert await seed.count("agent_runs", world.tenant_id) == 0
    assert model.requests == []


@pytest.mark.usefixtures("worker")
async def test_ac14_a_missing_version_fails_the_workflow_without_retries(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    handle = await _start(temporal, _input(world, uuid.uuid4(), world.requester.user_id))
    with pytest.raises(WorkflowFailureError) as caught:
        await handle.result()
    activity_error = caught.value.cause
    assert isinstance(activity_error, ActivityError)
    cause = activity_error.cause
    assert isinstance(cause, ApplicationError)
    assert (cause.type, cause.non_retryable) == ("NotFound", True)
    assert await _scheduled_activities(handle) == ["screening.create_run"]
    history = await handle.fetch_history()
    started = [e for e in history.events if e.HasField("activity_task_started_event_attributes")]
    assert len(started) == 1
    assert await seed.count("agent_runs", world.tenant_id) == 0


@pytest.mark.usefixtures("worker")
async def test_ac14_the_workflow_completes_with_a_recorded_agent_result(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    handle = await _start(temporal, screening_input(event))
    outcome = await handle.result()
    assert isinstance(outcome, ScreeningOutcome)
    assert outcome.status == "completed"
    assert outcome.code is None
    assert outcome.run_id is not None
    assert await _row(seed, outcome.run_id) == ("completed", None)
    [result] = await seed.rows(
        "SELECT id, created_by_kind, agent_run_id FROM screening_results WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert outcome.screening_result_id == str(result["id"])
    assert (result["created_by_kind"], str(result["agent_run_id"])) == ("agent", outcome.run_id)
    assert await _scheduled_activities(handle) == ["screening.create_run", "screening.screen"]
    assert await seed.item_status(world.item_id) == "received"  # the agent only proposes
    [usage] = await seed.rows(
        "SELECT outcome FROM usage_records WHERE tenant_id = $1", world.tenant_id
    )
    assert usage["outcome"] == "ok"  # AC-16


@pytest.mark.usefixtures("worker")
async def test_ac15_a_fabricated_citation_is_recorded_unverified_through_the_workflow(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    model.reply = lambda request: json.dumps(
        {
            "action": "ready_for_review",
            "confidence": 0.9,
            "rationale": "Looks fine.",
            "citations": [{"cell": "Z999", "value": "1.00"}],
            "unverified": [],
        }
    )
    event = await _created_event(seed, world)
    outcome = await _execute(temporal, screening_input(event))
    assert outcome.status == "completed"
    [result] = await seed.rows(
        "SELECT action, citations::text AS citations, unverified FROM screening_results "
        "WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert result["action"] == "needs_revision"
    [citation] = json.loads(result["citations"])
    assert (citation["cell"], citation["verified"]) == ("Z999", False)
    assert result["unverified"]


@pytest.mark.usefixtures("worker")
async def test_ac14_invalid_output_twice_escalates_with_no_result(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    model.reply = lambda request: INVALID
    event = await _created_event(seed, world)
    handle = await _start(temporal, screening_input(event))
    outcome = await handle.result()
    assert isinstance(outcome, ScreeningOutcome)
    assert (outcome.status, outcome.code, outcome.screening_result_id) == ("escalated", None, None)
    assert outcome.run_id is not None
    assert await _row(seed, outcome.run_id) == ("escalated", None)
    assert await seed.count("screening_results", world.tenant_id) == 0
    assert len(model.requests) == 2
    assert "agent_run.escalated" in await seed.actions(world.tenant_id)
    assert await _scheduled_activities(handle) == ["screening.create_run", "screening.screen"]


@pytest.mark.usefixtures("worker")
async def test_ac17_a_terminal_error_fails_the_run_and_the_workflow_returns_the_failed_outcome(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    given = screening_input(event)
    # The person stays a firm member but leaves the engagement: authorisation (ADR-025) refuses.
    await seed.unmember(world.engagement_id, world.requester)
    handle = await _start(temporal, given)
    outcome = await handle.result()  # returned, not raised
    assert isinstance(outcome, ScreeningOutcome)
    assert (outcome.status, outcome.code, outcome.screening_result_id) == (
        "failed",
        "forbidden",
        None,
    )
    assert outcome.run_id is not None
    assert await _row(seed, outcome.run_id) == ("failed", "forbidden")
    assert await seed.count("screening_results", world.tenant_id) == 0
    assert model.requests == []
    names = await _scheduled_activities(handle)
    assert names == ["screening.create_run", "screening.screen", "screening.fail_run"]
    # Not retried: the terminal error is non-retryable.
    history = await handle.fetch_history()
    screens = [
        e
        for e in history.events
        if e.HasField("activity_task_scheduled_event_attributes")
        and e.activity_task_scheduled_event_attributes.activity_type.name == "screening.screen"
    ]
    assert len(screens) == 1
    assert (
        len([e for e in history.events if e.HasField("activity_task_started_event_attributes")])
        == 3
    )


@pytest.mark.usefixtures("worker")
async def test_ac17_a_lost_initiator_ends_the_run_as_initiator_inactive(
    seed: Seeder, world: World, temporal: Client, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = activities.create_screening_run

    async def create_then_lose_the_person(
        tenant_id: uuid.UUID,
        evidence_version_id: uuid.UUID,
        source_event_id: uuid.UUID,
        requested_by: uuid.UUID | None,
    ) -> uuid.UUID | None:
        run_id = await real(tenant_id, evidence_version_id, source_event_id, requested_by)
        await seed.revoke(world.requester)
        return run_id

    event = await _created_event(seed, world)
    monkeypatch.setattr(activities, "create_screening_run", create_then_lose_the_person)
    outcome = await _execute(temporal, screening_input(event))
    assert outcome.status == "failed"
    assert outcome.code == "initiator_inactive"
    assert outcome.run_id is not None
    assert await _row(seed, outcome.run_id) == ("failed", "initiator_inactive")
    assert model.requests == []
    assert await seed.count("screening_results", world.tenant_id) == 0


@pytest.mark.usefixtures("worker")
async def test_ac14_a_provider_error_is_retried_then_the_run_ends_provider_unavailable(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    def down(request: ModelRequest) -> str:
        raise ProviderError(LEAKED)

    model.reply = down
    event = await _created_event(seed, world)
    handle = await _start(temporal, screening_input(event))
    outcome = await handle.result()
    assert isinstance(outcome, ScreeningOutcome)
    assert (outcome.status, outcome.code, outcome.screening_result_id) == (
        "failed",
        "provider_unavailable",
        None,
    )
    assert outcome.run_id is not None
    assert await _row(seed, outcome.run_id) == ("failed", "provider_unavailable")
    assert len(model.requests) == 4  # four attempts, then the workflow gives up
    usage = await seed.rows(
        "SELECT outcome FROM usage_records WHERE tenant_id = $1", world.tenant_id
    )
    assert [u["outcome"] for u in usage] == ["provider_error"] * 4
    assert await seed.count("screening_results", world.tenant_id) == 0
    names = await _scheduled_activities(handle)
    assert names[0] == "screening.create_run"
    assert names[-1] == "screening.fail_run"
    assert LEAKED not in json.dumps(outcome.__dict__)


@pytest.mark.usefixtures("worker")
async def test_ac14_another_error_is_retried_then_the_run_ends_internal_error(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    def broken(request: ModelRequest) -> str:
        raise ValueError(LEAKED)

    model.reply = broken
    event = await _created_event(seed, world)
    outcome = await _execute(temporal, screening_input(event))
    assert (outcome.status, outcome.code) == ("failed", "internal_error")
    assert outcome.run_id is not None
    assert await _row(seed, outcome.run_id) == ("failed", "internal_error")
    assert len(model.requests) == 4


@pytest.mark.usefixtures("worker")
async def test_ac14_fail_run_is_retried_until_it_succeeds(
    seed: Seeder, world: World, temporal: Client, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = activities.fail_run
    calls = {"n": 0}

    async def flaky(tenant_id: uuid.UUID, run_id: uuid.UUID, code: str) -> bool:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ConnectionError(LEAKED)
        return await real(tenant_id, run_id, code)

    monkeypatch.setattr(activities, "fail_run", flaky)
    event = await _created_event(seed, world)
    given = screening_input(event)
    await seed.unmember(world.engagement_id, world.requester)
    outcome = await _execute(temporal, given)
    assert (outcome.status, outcome.code) == ("failed", "forbidden")
    assert calls["n"] >= 3  # two failures, then it went through


@pytest.mark.usefixtures("worker")
async def test_ac14_cancelling_the_workflow_fails_the_run_as_cancelled(
    seed: Seeder, world: World, temporal: Client, gate: Gate
) -> None:
    event = await _created_event(seed, world)
    handle = await _start(temporal, screening_input(event))
    await asyncio.wait_for(gate.started.wait(), timeout=20)
    await handle.cancel()
    with pytest.raises(WorkflowFailureError) as caught:
        await handle.result()
    assert isinstance(caught.value.cause, CancelledError)
    [run] = await seed.rows(
        "SELECT id, status, failure_code FROM agent_runs WHERE tenant_id = $1", world.tenant_id
    )
    assert (run["status"], run["failure_code"]) == ("failed", "cancelled")
    names = await _scheduled_activities(handle)
    assert names[-1] == "screening.fail_run"
    # The model call that was in flight finishes after the cancellation: it records nothing.
    gate.release.set()
    await asyncio.sleep(1.0)
    assert await seed.count("screening_results", world.tenant_id) == 0
    [after] = await seed.rows(
        "SELECT status, failure_code FROM agent_runs WHERE tenant_id = $1", world.tenant_id
    )
    assert (after["status"], after["failure_code"]) == ("failed", "cancelled")


# --- workflow history ----------------------------------------------------------------------------


def _payloads(node: object) -> list[Payload]:
    found: list[Payload] = []
    if isinstance(node, dict):
        mapping = cast("dict[str, object]", node)
        metadata = mapping.get("metadata")
        data = mapping.get("data")
        if isinstance(metadata, dict) and isinstance(data, str):
            meta = cast("dict[str, str]", metadata)
            found.append(
                Payload(
                    metadata={k: base64.b64decode(v) for k, v in meta.items()},
                    data=base64.b64decode(data),
                )
            )
        for value in mapping.values():
            found.extend(_payloads(value))
    elif isinstance(node, list):
        for item in cast("list[object]", node):
            found.extend(_payloads(item))
    return found


@pytest.mark.usefixtures("worker")
async def test_ac19_history_payloads_hold_identifiers_only(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    event = await _created_event(seed, world)
    handle = await _start(temporal, screening_input(event))
    outcome = await handle.result()
    assert isinstance(outcome, ScreeningOutcome)
    assert outcome.status == "completed"
    history = await handle.fetch_history()
    sealed = [
        p for p in _payloads(json.loads(history.to_json())) if ENCODING in p.metadata.values()
    ]
    # The workflow's and each of two activities' input and result.
    assert len(sealed) >= 6
    opened = await payload_codec().decode(sealed)
    texts = [p.data.decode(errors="replace") for p in opened]
    joined = "\n".join(texts)
    # Identifiers are there: the payloads are real and were opened ...
    assert str(world.tenant_id) in joined
    assert outcome.run_id is not None
    assert outcome.run_id in joined
    # ... and nothing from the ledger or the client is.
    names = [line.account_name for line in TB.lines]
    amounts = [str(line.debit) for line in TB.lines] + [str(line.credit) for line in TB.lines]
    amounts += [str(TB.total_debits), str(TB.total_credits)]
    for name in [*names, ENTITY.name]:
        assert name not in joined, name
    for amount in amounts:
        if amount != "0.00":
            assert amount not in joined, amount
    rationale = await seed.value(
        "SELECT rationale FROM screening_results WHERE tenant_id = $1", world.tenant_id
    )
    assert str(rationale) not in joined
