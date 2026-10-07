"""SPEC-003 AC-6, AC-7, AC-13, AC-14: the retrieval and screening workflows wait for a work slot
against a local Temporal with the real worker (TASK-018 interface contract 018b, "Workflows", and
contract revision 1; ADR-071, ADR-017, ADR-090).

A firm is held at its cap by seeding a slot for it in the ledger (a "blocker") or by setting its
cap to zero; the maximum wait is made tiny through `ABACUS_WORK_CLASSES`. The retrieval is started
and read through the API (`POST` and `GET` of a retrieval), the screening through `dispatch`'s
queue. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
import pytest
from temporalio import activity
from temporalio.api.enums.v1 import EventType
from temporalio.client import Client, WorkflowFailureError, WorkflowHandle
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.worker import Worker

from abacus.ai_gateway import (
    FakeModel,
    ModelRequest,
    ModelResponse,
    configure_provider,
)
from abacus.kernel.config import settings
from abacus.kernel.db import configure_relay_engine
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents import api as agents
from abacus.modules.agents.api import SCREEN_PROMPT, ScreeningWorkflow, screening_responder
from abacus.modules.agents.screenings import EVIDENCE_VERSION_CREATED, screening_input
from abacus.modules.agents.workflow_types import ScreeningOutcome
from abacus.modules.connections import api as connections
from abacus.modules.connections.api import RetrievalWorkflow
from abacus.modules.connections.workflow_types import RetrievalInput
from abacus.worker.__main__ import build_workers
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.synthetic.connector_fixtures import write_fault, write_trial_balance

from .support import (
    ENTITY,
    ENTITY_NAME,
    PERIOD,
    TB,
    Migrated,
    Seeder,
    World,
    make_world,
    retrieve,
)

QUEUE = f"slots-wf-{uuid.uuid4().hex[:12]}"
CLASSES = ("interactive", "time_sensitive", "background", "batch")
Json = dict[str, object]
LEDGER = ("work_slots", "work_waiters", "work_grants")


# --- fixtures ------------------------------------------------------------------------------------

CLEAR = {
    "work_slots": "DELETE FROM work_slots",
    "work_waiters": "DELETE FROM work_waiters",
    "work_grants": "DELETE FROM work_grants",
}


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
async def empty_ledger(seed: Seeder) -> None:
    for table in LEDGER:
        await seed.run(CLEAR[table])


@pytest.fixture
def caps(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Set one class's caps now (the others keep defaults); the activities read them per call."""

    def apply(work_class: str, **overrides: int) -> None:
        full = {
            name: {
                "max_activities": 10,
                "max_workflow_tasks": 10,
                "firm_cap": 20,
                "engagement_cap": 10,
                "class_capacity": 50,
                "max_wait_seconds": 120,
                "admission_reserve_pct": 0,
            }
            for name in CLASSES
        }
        full[work_class].update(overrides)
        monkeypatch.setenv("ABACUS_WORK_CLASSES", json.dumps(full))
        settings.cache_clear()

    return apply


@asynccontextmanager
async def _serving() -> AsyncGenerator[list[Worker]]:
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
async def worker(temporal: Client, caps: Callable[..., None]) -> AsyncIterator[list[Worker]]:
    async with _serving() as built:
        yield built


async def _until[T](
    probe: Callable[[], Awaitable[T | None]], *, seconds: float = 45, what: str = "condition"
) -> T:
    try:
        async with asyncio.timeout(seconds):
            while True:
                found = await probe()
                if found is not None:
                    return found
                await asyncio.sleep(0.2)
    except TimeoutError:
        raise AssertionError(f"timed out waiting for {what}") from None


async def _block(seed: Seeder, tenant: uuid.UUID, work_class: str) -> str:
    """A slot held by `tenant`'s other work, with a live lease. Returns its holder."""
    holder = f"blocker-{uuid.uuid4()}"
    await seed.run(
        "INSERT INTO work_slots (tenant_id, holder, work_class, acquired_at, lease_until) "
        "VALUES ($1, $2, $3, now(), now() + interval '1 hour')",
        tenant,
        holder,
        work_class,
    )
    return holder


async def _unblock(seed: Seeder, holder: str) -> None:
    await seed.run("DELETE FROM work_slots WHERE holder = $1", holder)


async def _ledger_empty(seed: Seeder, tenant: uuid.UUID) -> bool:
    return (
        await seed.value("SELECT count(*) FROM work_slots WHERE tenant_id = $1", tenant) == 0
        and await seed.value("SELECT count(*) FROM work_waiters WHERE tenant_id = $1", tenant) == 0
    )


async def _activities(handle: WorkflowHandle[Any, Any]) -> list[str]:  # a recorded call
    history = await handle.fetch_history()
    return [
        e.activity_task_scheduled_event_attributes.activity_type.name
        for e in history.events
        if e.HasField("activity_task_scheduled_event_attributes")
    ]


async def _timers(handle: WorkflowHandle[Any, Any]) -> int:  # a recorded call
    history = await handle.fetch_history()
    return len([e for e in history.events if e.event_type == EventType.EVENT_TYPE_TIMER_STARTED])


# =================================================================================================
# retrieval, started and read through the API
# =================================================================================================


async def _subject(seed: Seeder, world: World) -> str:
    return str(
        await seed.value("SELECT idp_subject FROM users WHERE id = $1", world.requester.user_id)
    )


ApiFor = Callable[[World], Awaitable["Api"]]


class Api:
    def __init__(self, http: httpx.AsyncClient, token: str, world: World) -> None:
        self.http, self.token, self.world = http, token, world

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def post(self) -> Json:
        response = await self.http.post(
            f"/v1/engagements/{self.world.engagement_id}/retrievals",
            json={
                "request_item_id": str(self.world.item_id),
                "period_start": PERIOD.start.isoformat(),
                "period_end": PERIOD.end.isoformat(),
            },
            headers=self._headers(),
        )
        assert response.status_code == 202, response.text
        return cast(Json, response.json())

    async def get(self, run_id: object) -> Json:
        response = await self.http.get(
            f"/v1/engagements/{self.world.engagement_id}/retrievals/{run_id}",
            headers=self._headers(),
        )
        assert response.status_code == 200, response.text
        return cast(Json, response.json())

    async def until(self, run_id: object, predicate: Callable[[Json], bool]) -> Json:
        async def probe() -> Json | None:
            found = await self.get(run_id)
            return found if predicate(found) else None

        return await _until(probe, what="the run's status")


@pytest.fixture
def api_for(http: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder) -> ApiFor:
    async def make(world: World) -> Api:
        return Api(http, idp.token(await _subject(seed, world)), world)

    return make


@pytest.fixture
async def api(api_for: ApiFor, world: World) -> Api:
    return await api_for(world)


def _retrieval_handle(
    temporal: Client, run_id: object
) -> WorkflowHandle[RetrievalWorkflow, connections.RetrievalOutcome]:
    return temporal.get_workflow_handle_for(
        RetrievalWorkflow.run, connections.workflow_id(uuid.UUID(str(run_id)))
    )


@pytest.mark.usefixtures("worker")
async def test_ac13_a_run_waits_while_its_firm_is_at_cap_and_the_get_shows_queued_with_a_reason(
    seed: Seeder, world: World, temporal: Client, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    await _block(seed, world.tenant_id, "interactive")
    started = await api.post()
    run_id = started["sync_run_id"]
    queued = await api.until(run_id, lambda r: r["status"] == "queued")
    assert queued["queued_reason"] == "firm_cap"
    assert queued["estimated_start_at"] is None  # no recent grants: unknown, still queued
    assert queued["failure_code"] is None
    assert queued["finished_at"] is None
    assert queued["evidence_version_id"] is None
    # waiting is not running, and not failed: the workflow is open, the stored run still running
    handle = _retrieval_handle(temporal, run_id)
    assert (await handle.describe()).status is not None
    assert (await handle.describe()).close_time is None
    row = await seed.rows("SELECT status FROM sync_runs WHERE id = $1", uuid.UUID(str(run_id)))
    assert row[0]["status"] == "running"
    assert await seed.count("evidence_versions", world.tenant_id) == 0
    assert "sync_run.queued" in await seed.actions(world.tenant_id)
    # the pipeline has not started: only slot asks so far
    assert set(await _activities(handle)) == {"retrieval.acquire_slot"}


@pytest.mark.usefixtures("worker")
async def test_ac13_the_estimate_is_shown_when_the_class_has_recent_grants(
    seed: Seeder, world: World, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    await _block(seed, world.tenant_id, "interactive")
    for _ in range(5):
        await seed.run(
            "INSERT INTO work_grants (tenant_id, work_class, granted_at) "
            "VALUES ($1, 'interactive', now() - interval '1 minute')",
            world.tenant_id,
        )
    run_id = (await api.post())["sync_run_id"]
    queued = await api.until(run_id, lambda r: r["status"] == "queued")
    estimate = datetime.fromisoformat(str(queued["estimated_start_at"]))
    assert (estimate.second, estimate.microsecond) == (0, 0)
    assert estimate > datetime.now(UTC) - timedelta(seconds=1)
    assert estimate < datetime.now(UTC) + timedelta(minutes=10)


@pytest.mark.usefixtures("worker")
async def test_ac13_a_queued_run_is_never_reported_as_running_while_it_waits(
    seed: Seeder, world: World, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    await _block(seed, world.tenant_id, "interactive")
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "queued")
    for _ in range(10):
        assert (await api.get(run_id))["status"] == "queued"
        await asyncio.sleep(0.2)


@pytest.mark.usefixtures("worker")
async def test_ac13_a_second_post_while_the_run_is_queued_attaches_to_it_and_starts_nothing(
    seed: Seeder, world: World, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    await _block(seed, world.tenant_id, "interactive")
    first = (await api.post())["sync_run_id"]
    await api.until(first, lambda r: r["status"] == "queued")
    second = await api.post()  # a queued run is active, like a running one
    assert second["sync_run_id"] == first
    assert second["status"] == "queued"
    assert (
        await seed.value("SELECT count(*) FROM sync_runs WHERE tenant_id = $1", world.tenant_id)
        == 1
    )


@pytest.mark.usefixtures("worker")
async def test_ac6_the_run_proceeds_to_success_when_a_slot_frees_and_resumed_is_audited(
    seed: Seeder, world: World, temporal: Client, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    blocker = await _block(seed, world.tenant_id, "interactive")
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "queued")
    await _unblock(seed, blocker)
    done = await api.until(run_id, lambda r: r["status"] == "succeeded")
    assert (done["queued_reason"], done["estimated_start_at"]) == (None, None)
    assert done["evidence_version_id"] is not None
    actions = await seed.actions(world.tenant_id)
    assert actions.index("sync_run.queued") < actions.index("sync_run.resumed")
    assert actions.index("sync_run.resumed") < actions.index("sync_run.raw_stored")
    assert actions.count("sync_run.queued") == 1  # polling wrote nothing more
    assert actions.count("sync_run.resumed") == 1
    handle = _retrieval_handle(temporal, run_id)
    names = await _activities(handle)
    assert names.count("retrieval.acquire_slot") >= 2  # it asked again after waiting
    assert await _timers(handle) >= 1  # waiting is a durable timer, not a held worker
    assert names[-1] == "retrieval.release_slot"
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac6_a_run_with_free_slots_asks_once_and_never_sleeps(
    seed: Seeder, world: World, temporal: Client, api: Api
) -> None:
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "succeeded")
    handle = _retrieval_handle(temporal, run_id)
    names = await _activities(handle)
    assert names == [
        "retrieval.acquire_slot",
        "retrieval.pull_raw",
        "retrieval.normalise_raw",
        "retrieval.validate_run",
        "retrieval.snapshot",
        "retrieval.render",
        "retrieval.release_slot",
    ]
    assert await _timers(handle) == 0
    actions = await seed.actions(world.tenant_id)
    assert "sync_run.queued" not in actions
    assert "sync_run.resumed" not in actions
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac14_a_run_waiting_past_the_max_wait_fails_capacity_timeout(
    seed: Seeder, world: World, temporal: Client, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=0, max_wait_seconds=2)  # a paused firm, a tiny maximum wait
    run_id = (await api.post())["sync_run_id"]
    failed = await api.until(run_id, lambda r: r["status"] == "failed")
    assert failed["failure_code"] == "capacity_timeout"
    assert (failed["queued_reason"], failed["estimated_start_at"]) == (None, None)
    assert failed["finished_at"] is not None
    assert failed["evidence_version_id"] is None
    outcome = await _retrieval_handle(temporal, run_id).result()
    assert (outcome.status, outcome.code) == ("failed", "capacity_timeout")
    actions = await seed.actions(world.tenant_id)
    assert actions.count("sync_run.queued") >= 1
    assert actions.count("sync_run.failed") == 1  # through the audited fail path, never silent
    assert "sync_run.raw_stored" not in actions
    assert await seed.count("evidence_versions", world.tenant_id) == 0
    assert await _ledger_empty(seed, world.tenant_id)
    assert (await _activities(_retrieval_handle(temporal, run_id)))[-2:] == [
        "retrieval.fail_run",
        "retrieval.release_slot",
    ]


@pytest.mark.usefixtures("worker")
async def test_ac14_the_wait_is_not_cut_short_before_the_max_wait(
    seed: Seeder, world: World, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=0, max_wait_seconds=60)
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "queued")
    await asyncio.sleep(4)
    assert (await api.get(run_id))["status"] == "queued"


@pytest.mark.usefixtures("worker")
async def test_ac14_a_waiter_that_waited_gets_its_slot_before_the_max_wait_is_over(
    seed: Seeder, world: World, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1, max_wait_seconds=30)
    blocker = await _block(seed, world.tenant_id, "interactive")
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "queued")
    await _unblock(seed, blocker)
    done = await api.until(run_id, lambda r: r["status"] in ("succeeded", "failed"))
    assert done["status"] == "succeeded"


@pytest.mark.usefixtures("worker")
async def test_ac6_the_slot_is_held_while_running_and_released_on_success(
    seed: Seeder, world: World, api: Api
) -> None:
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "succeeded")
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac6_the_slot_is_released_when_the_run_fails(
    seed: Seeder, world: World, api: Api
) -> None:
    for path in (world.directory / str(world.connection_id)).iterdir():
        path.unlink()  # no data: the pull fails for good
    run_id = (await api.post())["sync_run_id"]
    failed = await api.until(run_id, lambda r: r["status"] in ("failed", "failed_validation"))
    assert failed["failure_code"] == "no_data"
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac6_the_slot_is_held_by_a_running_run(
    seed: Seeder, world: World, temporal: Client, api: Api
) -> None:
    write_fault(world.directory, world.connection_id, PERIOD)  # the pull keeps failing: retries
    run_id = (await api.post())["sync_run_id"]

    async def holding() -> list[str] | None:
        rows = await seed.rows(
            "SELECT holder FROM work_slots WHERE tenant_id = $1", world.tenant_id
        )
        return [str(r["holder"]) for r in rows] or None

    [holder] = await _until(holding, what="the slot")
    handle = _retrieval_handle(temporal, run_id)
    description = await handle.describe()
    assert holder == f"{description.id}:{description.run_id}"
    assert (await api.get(run_id))["status"] == "running"
    await handle.cancel()
    with pytest.raises(WorkflowFailureError):
        await handle.result()


@pytest.mark.usefixtures("worker")
async def test_ac6_the_slot_is_released_when_the_workflow_is_cancelled_mid_run(
    seed: Seeder, world: World, temporal: Client, api: Api
) -> None:
    write_fault(world.directory, world.connection_id, PERIOD)
    run_id = (await api.post())["sync_run_id"]
    handle = _retrieval_handle(temporal, run_id)

    async def holding() -> bool | None:
        return None if await _ledger_empty(seed, world.tenant_id) else True

    await _until(holding, what="the slot")
    await handle.cancel()
    with pytest.raises(WorkflowFailureError) as raised:
        await handle.result()
    assert isinstance(raised.value.cause, CancelledError)
    assert await _ledger_empty(seed, world.tenant_id)
    got = await api.get(run_id)
    assert (got["status"], got["failure_code"]) == ("failed", "cancelled")
    assert (await _activities(handle))[-1] == "retrieval.release_slot"


@pytest.mark.usefixtures("worker")
async def test_ac14_a_run_cancelled_while_queued_ends_cancelled_with_the_queue_fields_cleared(
    seed: Seeder, world: World, temporal: Client, api: Api, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    await _block(seed, world.tenant_id, "interactive")
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "queued")
    handle = _retrieval_handle(temporal, run_id)
    await handle.cancel()
    with pytest.raises(WorkflowFailureError) as raised:
        await handle.result()
    assert isinstance(raised.value.cause, CancelledError)
    got = await api.get(run_id)
    assert (got["status"], got["failure_code"]) == ("failed", "cancelled")
    assert (got["queued_reason"], got["estimated_start_at"]) == (None, None)
    assert got["finished_at"] is not None
    # the blocker is another run's: only ours is gone
    assert await seed.value("SELECT count(*) FROM work_slots") == 1
    assert await seed.value("SELECT count(*) FROM work_waiters") == 0
    actions = await seed.actions(world.tenant_id)
    assert "sync_run.queued" in actions
    assert actions.count("sync_run.failed") == 1
    assert (await _activities(handle))[-2:] == ["retrieval.fail_run", "retrieval.release_slot"]


@pytest.mark.usefixtures("worker")
async def test_ac7_an_engagement_at_its_cap_waits_while_a_sibling_engagement_runs(
    seed: Seeder, world: World, api: Api, api_for: ApiFor, caps: Callable[..., None]
) -> None:
    caps("interactive", engagement_cap=1)
    await seed.run(
        "INSERT INTO work_slots (tenant_id, holder, engagement_id, work_class, acquired_at, "
        "lease_until) VALUES ($1, 'busy', $2, 'interactive', now(), now() + interval '1 hour')",
        world.tenant_id,
        world.engagement_id,
    )
    run_id = (await api.post())["sync_run_id"]
    queued = await api.until(run_id, lambda r: r["status"] == "queued")
    assert queued["queued_reason"] == "engagement_cap"
    # another engagement of the same firm is not held up
    entity = await seed.entity(world.tenant_id)
    sibling = await seed.engagement(world.tenant_id, entity, world.requester.user_id)
    await seed.member(sibling, world.requester, "staff")
    item = await seed.item(world.tenant_id, sibling, world.requester.user_id)
    connection = await seed.connection(world.tenant_id, entity)
    write_trial_balance(
        world.directory, connection, TB, period_start=ENTITY.period_start, entity_name=ENTITY_NAME
    )
    siblings = await api_for(
        World(world.tenant_id, sibling, entity, item, connection, world.requester, world.directory)
    )
    done = await siblings.until(
        (await siblings.post())["sync_run_id"], lambda r: r["status"] in ("succeeded", "failed")
    )
    assert done["status"] == "succeeded"
    assert (await api.get(run_id))["status"] == "queued"


@pytest.mark.usefixtures("worker")
async def test_ac6_another_firms_run_proceeds_while_this_firm_waits(
    seed: Seeder, world: World, api: Api, api_for: ApiFor, caps: Callable[..., None]
) -> None:
    caps("interactive", firm_cap=1)
    await _block(seed, world.tenant_id, "interactive")
    run_id = (await api.post())["sync_run_id"]
    await api.until(run_id, lambda r: r["status"] == "queued")
    elsewhere = await api_for(await make_world(seed, world.directory))
    done = await elsewhere.until(
        (await elsewhere.post())["sync_run_id"], lambda r: r["status"] in ("succeeded", "failed")
    )
    assert done["status"] == "succeeded"
    assert (await api.get(run_id))["status"] == "queued"  # this firm still waits


# --- release must never change the run's outcome -------------------------------------------------


async def test_ac6_a_release_that_keeps_failing_does_not_change_the_runs_outcome(
    seed: Seeder, world: World, temporal: Client, caps: Callable[..., None]
) -> None:
    caps("interactive")

    @activity.defn(name="retrieval.release_slot")
    async def broken(input: RetrievalInput) -> None:
        raise ApplicationError("database down", type="OperationalError", non_retryable=True)

    others = [a for a in connections.ACTIVITIES if not a.__name__.startswith("release_slot")]
    started = await connections.start_retrieval(
        world.requester.context(),
        engagement_id=world.engagement_id,
        request_item_id=world.item_id,
        period=PERIOD,
    )
    async with Worker(
        temporal,
        task_queue=queue_for("interactive"),
        workflows=[RetrievalWorkflow],
        activities=[broken, *others],
    ):
        outcome = await temporal.execute_workflow(
            RetrievalWorkflow.run,
            RetrievalInput(str(world.tenant_id), str(started.run_id)),
            id=f"test-{uuid.uuid4()}",
            task_queue=queue_for("interactive"),
            execution_timeout=timedelta(seconds=90),
        )
    assert outcome.status == "succeeded"  # the release failure is swallowed
    row = await seed.rows("SELECT status FROM sync_runs WHERE id = $1", started.run_id)
    assert row[0]["status"] == "succeeded"


# =================================================================================================
# screening
# =================================================================================================


class Model:
    def __init__(self) -> None:
        fake = FakeModel()
        fake.respond(SCREEN_PROMPT, screening_responder)
        configure_provider(fake)


@pytest.fixture
def model() -> Iterator[Model]:
    yield Model()
    configure_provider(None)


async def _created_event(seed: Seeder, world: World) -> OutboxEvent:
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


async def _start_screening(
    temporal: Client, seed: Seeder, world: World
) -> WorkflowHandle[ScreeningWorkflow, ScreeningOutcome]:
    given = screening_input(await _created_event(seed, world))
    return await temporal.start_workflow(
        ScreeningWorkflow.run,
        given,
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("time_sensitive"),
        execution_timeout=timedelta(seconds=90),
    )


async def _agent_row(seed: Seeder, tenant: uuid.UUID) -> tuple[str, str | None, str | None]:
    rows = await seed.rows(
        "SELECT status, failure_code, queued_reason, estimated_start_at FROM agent_runs "
        "WHERE tenant_id = $1",
        tenant,
    )
    assert len(rows) == 1
    return str(rows[0]["status"]), rows[0]["failure_code"], rows[0]["queued_reason"]


@pytest.mark.usefixtures("worker")
async def test_ac13_a_screening_waits_while_its_firm_is_at_cap_and_the_run_is_marked_queued(
    seed: Seeder, world: World, temporal: Client, model: Model, caps: Callable[..., None]
) -> None:
    caps("time_sensitive", firm_cap=1)
    await _block(seed, world.tenant_id, "time_sensitive")
    handle = await _start_screening(temporal, seed, world)

    async def queued() -> bool | None:
        rows = await seed.rows(
            "SELECT queued_reason FROM agent_runs WHERE tenant_id = $1", world.tenant_id
        )
        return True if rows and rows[0]["queued_reason"] == "firm_cap" else None

    await _until(queued, what="the run to be marked queued")
    status, code, reason = await _agent_row(seed, world.tenant_id)
    assert (status, code, reason) == ("running", None, "firm_cap")
    assert await seed.count("screening_results", world.tenant_id) == 0
    assert "agent_run.queued" in await seed.actions(world.tenant_id)
    assert set(await _activities(handle)) == {"screening.create_run", "screening.acquire_slot"}
    await handle.cancel()
    with pytest.raises(WorkflowFailureError):
        await handle.result()


@pytest.mark.usefixtures("worker")
async def test_ac6_a_screening_proceeds_when_a_slot_frees_and_completes(
    seed: Seeder, world: World, temporal: Client, model: Model, caps: Callable[..., None]
) -> None:
    caps("time_sensitive", firm_cap=1)
    blocker = await _block(seed, world.tenant_id, "time_sensitive")
    handle = await _start_screening(temporal, seed, world)

    async def queued() -> bool | None:
        rows = await seed.rows(
            "SELECT queued_reason FROM agent_runs WHERE tenant_id = $1", world.tenant_id
        )
        return True if rows and rows[0]["queued_reason"] else None

    await _until(queued, what="the run to be marked queued")
    await _unblock(seed, blocker)
    outcome = await handle.result()
    assert outcome.status == "completed"
    assert await _agent_row(seed, world.tenant_id) == ("completed", None, None)
    actions = await seed.actions(world.tenant_id)
    assert actions.index("agent_run.queued") < actions.index("agent_run.resumed")
    assert actions.count("agent_run.queued") == 1
    assert actions.count("agent_run.resumed") == 1
    names = await _activities(handle)
    assert names[0] == "screening.create_run"
    assert names.count("screening.acquire_slot") >= 2
    assert names[-2:] == ["screening.screen", "screening.release_slot"]
    assert await _timers(handle) >= 1
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac14_a_screening_waiting_past_the_max_wait_fails_capacity_timeout(
    seed: Seeder, world: World, temporal: Client, model: Model, caps: Callable[..., None]
) -> None:
    caps("time_sensitive", firm_cap=0, max_wait_seconds=2)
    handle = await _start_screening(temporal, seed, world)
    outcome = await handle.result()
    assert (outcome.status, outcome.code) == ("failed", "capacity_timeout")
    assert await _agent_row(seed, world.tenant_id) == ("failed", "capacity_timeout", None)
    rows = await seed.rows(
        "SELECT estimated_start_at FROM agent_runs WHERE tenant_id = $1", world.tenant_id
    )
    assert rows[0]["estimated_start_at"] is None
    assert await seed.count("screening_results", world.tenant_id) == 0
    actions = await seed.actions(world.tenant_id)
    assert "agent_run.queued" in actions
    assert actions.count("agent_run.failed") == 1
    assert (await _activities(handle))[-2:] == ["screening.fail_run", "screening.release_slot"]
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac6_the_screening_slot_is_released_on_success(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    handle = await _start_screening(temporal, seed, world)
    outcome = await handle.result()
    assert outcome.status == "completed"
    assert await _activities(handle) == [
        "screening.create_run",
        "screening.acquire_slot",
        "screening.screen",
        "screening.release_slot",
    ]
    assert await _timers(handle) == 0
    assert await _ledger_empty(seed, world.tenant_id)


@pytest.mark.usefixtures("worker")
async def test_ac6_the_screening_slot_is_released_when_the_run_fails(
    seed: Seeder, world: World, temporal: Client, model: Model
) -> None:
    given = screening_input(await _created_event(seed, world))
    await seed.unmember(world.engagement_id, world.requester)  # authorisation refuses the screen
    handle = await temporal.start_workflow(
        ScreeningWorkflow.run,
        given,
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("time_sensitive"),
        execution_timeout=timedelta(seconds=90),
    )
    outcome = await handle.result()
    assert (outcome.status, outcome.code) == ("failed", "forbidden")
    assert (await _activities(handle))[-2:] == ["screening.fail_run", "screening.release_slot"]
    assert await _ledger_empty(seed, world.tenant_id)


class Gate:
    def __init__(self) -> None:
        self.inner = FakeModel()
        self.inner.respond(SCREEN_PROMPT, screening_responder)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.started.set()
        await self.release.wait()
        return await self.inner.complete(request)


@pytest.mark.usefixtures("worker")
async def test_ac6_the_screening_slot_is_released_when_the_workflow_is_cancelled(
    seed: Seeder, world: World, temporal: Client
) -> None:
    gate = Gate()
    configure_provider(gate)
    try:
        handle = await _start_screening(temporal, seed, world)
        await asyncio.wait_for(gate.started.wait(), timeout=30)
        assert not await _ledger_empty(seed, world.tenant_id)  # held while it screens
        await handle.cancel()
        with pytest.raises(WorkflowFailureError) as raised:
            await handle.result()
        assert isinstance(raised.value.cause, CancelledError)
        assert await _agent_row(seed, world.tenant_id) == ("failed", "cancelled", None)
        assert await _ledger_empty(seed, world.tenant_id)
        assert (await _activities(handle))[-2:] == ["screening.fail_run", "screening.release_slot"]
    finally:
        gate.release.set()
        configure_provider(None)


@pytest.mark.usefixtures("worker")
async def test_ac14_a_screening_cancelled_while_queued_ends_cancelled_with_queue_fields_cleared(
    seed: Seeder, world: World, temporal: Client, model: Model, caps: Callable[..., None]
) -> None:
    caps("time_sensitive", firm_cap=1)
    await _block(seed, world.tenant_id, "time_sensitive")
    handle = await _start_screening(temporal, seed, world)

    async def queued() -> bool | None:
        rows = await seed.rows(
            "SELECT queued_reason FROM agent_runs WHERE tenant_id = $1", world.tenant_id
        )
        return True if rows and rows[0]["queued_reason"] else None

    await _until(queued, what="the run to be marked queued")
    await handle.cancel()
    with pytest.raises(WorkflowFailureError) as raised:
        await handle.result()
    assert isinstance(raised.value.cause, CancelledError)
    assert await _agent_row(seed, world.tenant_id) == ("failed", "cancelled", None)
    rows = await seed.rows(
        "SELECT estimated_start_at FROM agent_runs WHERE tenant_id = $1", world.tenant_id
    )
    assert rows[0]["estimated_start_at"] is None
    assert await seed.value("SELECT count(*) FROM work_waiters") == 0
    assert (await _activities(handle))[-2:] == ["screening.fail_run", "screening.release_slot"]


@pytest.mark.usefixtures("worker")
async def test_ac6_a_skipped_screening_takes_no_slot_and_never_waits(
    seed: Seeder, world: World, temporal: Client, model: Model, caps: Callable[..., None]
) -> None:
    caps("time_sensitive", firm_cap=0)  # would wait forever if it asked
    event = await _created_event(seed, world)
    given = screening_input(
        OutboxEvent(
            event.event_id,
            event.tenant_id,
            event.event_type,
            {**event.payload, "requested_by": None},
        )
    )
    handle = await temporal.start_workflow(
        ScreeningWorkflow.run,
        given,
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("time_sensitive"),
        execution_timeout=timedelta(seconds=30),
    )
    outcome = await handle.result()
    assert outcome.status == "skipped"
    assert await _activities(handle) == ["screening.create_run"]
    assert await seed.value("SELECT count(*) FROM work_waiters") == 0


async def test_ac6_a_screening_release_that_keeps_failing_does_not_change_the_outcome(
    seed: Seeder, world: World, temporal: Client, model: Model, caps: Callable[..., None]
) -> None:
    caps("time_sensitive")

    @activity.defn(name="screening.release_slot")
    async def broken(input: agents.ScreeningInput) -> None:
        raise ApplicationError("database down", type="OperationalError", non_retryable=True)

    others = [a for a in agents.ACTIVITIES if not a.__name__.startswith("release_slot")]
    given = screening_input(await _created_event(seed, world))
    async with Worker(
        temporal,
        task_queue=queue_for("time_sensitive"),
        workflows=[ScreeningWorkflow],
        activities=[broken, *others],
    ):
        outcome = await temporal.execute_workflow(
            ScreeningWorkflow.run,
            given,
            id=f"test-{uuid.uuid4()}",
            task_queue=queue_for("time_sensitive"),
            execution_timeout=timedelta(seconds=90),
        )
    assert outcome.status == "completed"
