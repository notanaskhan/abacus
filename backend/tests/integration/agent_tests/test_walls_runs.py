"""AC-7, AC-8: runs acting for a person who is walled after they started (TASK-016 interface
contract, "Runs"; SPEC-002 §12).

The retrieval pipeline runs as a system context on behalf of the requester; screening runs as an
agent whose initiator is the requester. Walling the requester stops the next authorised step
(layer `wall`), and the run ends failed with code `forbidden`. A real retrieved trial balance
comes from the pipeline; the worker and Temporal are real for the workflow test.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import cast

import httpx
import pytest
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment
from temporalio.worker import Worker

from abacus.ai_gateway import FakeModel
from abacus.kernel.config import settings
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.agents.api import create_screening_run, load_agent_context, screen
from abacus.modules.connections.api import (
    ACTIVITIES,
    RetrievalInput,
    RetrievalOutcome,
    RetrievalWorkflow,
    StartedRun,
    load_system_context,
    normalise_raw,
    pull_raw,
    run_pipeline,
    start_retrieval,
)
from abacus.modules.identity.api import Forbidden, Resource, authorise
from abacus.worker.__main__ import build_workers
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import PERIOD, Person, Seeder, World, retrieve
from .walls_support import Net

QUEUE = f"walls-runs-{uuid.uuid4().hex[:12]}"
[PULL_ACTIVITY] = [a for a in ACTIVITIES if a.__name__.startswith("pull_raw")]


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture
async def admin(net: Net, world: World) -> Person:
    return await net.person(world.tenant_id, "firm_admin")


async def _wall_requester(net: Net, admin: Person, world: World) -> uuid.UUID:
    client_id = cast(
        uuid.UUID,
        await net.seed.value(
            "SELECT client_id FROM client_entities WHERE id = $1", world.entity_id
        ),
    )
    return await net.wall(admin, world.requester.user_id, client_id)


async def _started(world: World) -> uuid.UUID:
    started = await start_retrieval(
        world.requester.context(),
        engagement_id=world.engagement_id,
        request_item_id=world.item_id,
        period=PERIOD,
    )
    assert isinstance(started, StartedRun)
    return started.run_id


async def _run_row(seed: Seeder, run_id: uuid.UUID) -> tuple[str, str | None, object]:
    [row] = await seed.rows(
        "SELECT status, failure_code, raw_fingerprint FROM sync_runs WHERE id = $1", run_id
    )
    return str(row["status"]), cast("str | None", row["failure_code"]), row["raw_fingerprint"]


# --- retrieval: the platform acting for a person -------------------------------------------------


async def test_ac7_a_retrieval_for_a_person_walled_after_it_started_is_denied_at_its_next_step(
    net: Net, admin: Person, world: World
) -> None:
    run_id = await _started(world)
    system = await load_system_context(world.tenant_id, run_id)
    await _wall_requester(net, admin, world)
    with pytest.raises(Forbidden) as raised:
        await pull_raw(system)
    assert raised.value.layer == "wall"
    status, _, raw = await _run_row(net.seed, run_id)
    assert status == "running"
    assert raw is None  # nothing was pulled or stored


async def test_ac7_a_wall_between_two_stages_stops_the_next_one(
    net: Net, admin: Person, world: World
) -> None:
    run_id = await _started(world)
    system = await load_system_context(world.tenant_id, run_id)
    await pull_raw(system)  # not yet walled
    await _wall_requester(net, admin, world)
    with pytest.raises(Forbidden) as raised:
        await normalise_raw(system)
    assert raised.value.layer == "wall"
    assert (
        await net.seed.value(
            "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1", world.tenant_id
        )
        == 0
    )
    assert await net.seed.count("evidence_versions", world.tenant_id) == 0


async def test_ac7_the_whole_pipeline_is_denied_for_a_walled_requester(
    net: Net, admin: Person, world: World
) -> None:
    run_id = await _started(world)
    system = await load_system_context(world.tenant_id, run_id)
    await _wall_requester(net, admin, world)
    with pytest.raises(Forbidden):
        await run_pipeline(system)
    assert await net.seed.count("evidence_versions", world.tenant_id) == 0
    assert await net.seed.item_status(world.item_id) == "open"


async def test_ac7_the_stage_activity_fails_with_a_non_retryable_forbidden(
    net: Net, admin: Person, world: World
) -> None:
    run_id = await _started(world)
    await _wall_requester(net, admin, world)
    with pytest.raises(ApplicationError) as caught:
        await ActivityEnvironment().run(
            cast("Callable[[RetrievalInput], Awaitable[object]]", PULL_ACTIVITY),
            RetrievalInput(str(world.tenant_id), str(run_id)),
        )
    assert (caught.value.message, caught.value.type) == ("Forbidden", "Forbidden")
    assert caught.value.non_retryable is True


async def test_ac8_a_person_walled_from_another_client_still_completes_their_retrieval(
    net: Net, admin: Person, world: World
) -> None:
    other = await net.site(world.tenant_id, admin.user_id)
    await net.wall(admin, world.requester.user_id, other.client_id)
    result = await retrieve(world)
    assert await net.seed.item_status(world.item_id) == "received"
    assert result.evidence_version_id is not None


async def test_ac8_someone_elses_wall_does_not_stop_the_run(
    net: Net, admin: Person, world: World
) -> None:
    colleague = await net.person(world.tenant_id)
    client_id = cast(
        uuid.UUID,
        await net.seed.value(
            "SELECT client_id FROM client_entities WHERE id = $1", world.entity_id
        ),
    )
    await net.wall(admin, colleague.user_id, client_id)
    await retrieve(world)
    assert await net.seed.item_status(world.item_id) == "received"


async def test_ac9_after_removal_a_new_retrieval_completes(
    net: Net, admin: Person, world: World
) -> None:
    wall_id = await _wall_requester(net, admin, world)
    assert (await net.remove_wall(admin, wall_id)).status_code == 200
    await retrieve(world)
    assert await net.seed.item_status(world.item_id) == "received"


# --- retrieval over Temporal: the run ends failed, with code forbidden ---------------------------


@pytest.fixture(autouse=True)
def task_queue(monkeypatch: pytest.MonkeyPatch, fake_dir: object) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    yield
    settings.cache_clear()


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


@pytest.mark.usefixtures("worker")
async def test_ac7_a_retrieval_workflow_for_a_walled_person_ends_failed_with_code_forbidden(
    net: Net, admin: Person, world: World, temporal: Client
) -> None:
    run_id = await _started(world)
    await _wall_requester(net, admin, world)
    outcome = await temporal.execute_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=f"walls-{uuid.uuid4()}",
        task_queue=queue_for("interactive"),
        execution_timeout=timedelta(seconds=90),
    )
    assert isinstance(outcome, RetrievalOutcome)
    assert (outcome.status, outcome.code) == ("failed", "forbidden")
    status, code, raw = await _run_row(net.seed, run_id)
    assert (status, code, raw) == ("failed", "forbidden", None)
    assert await net.seed.item_status(world.item_id) == "open"


# --- screening: an agent acting for its initiator ------------------------------------------------


async def _ready(world: World) -> uuid.UUID:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    return run_id


async def _agent_row(seed: Seeder, run_id: uuid.UUID) -> tuple[str, str | None]:
    [row] = await seed.rows("SELECT status, failure_code FROM agent_runs WHERE id = $1", run_id)
    return str(row["status"]), cast("str | None", row["failure_code"])


async def test_ac7_an_agent_run_for_a_person_walled_after_it_started_ends_failed_forbidden(
    net: Net, admin: Person, world: World, fake_model: FakeModel
) -> None:
    run_id = await _ready(world)
    agent = await load_agent_context(world.tenant_id, run_id)
    await _wall_requester(net, admin, world)
    with pytest.raises(Forbidden) as raised:
        await screen(agent)
    assert raised.value.layer == "wall"
    assert await _agent_row(net.seed, run_id) == ("failed", "forbidden")
    assert await net.seed.count("screening_results", world.tenant_id) == 0
    assert await net.seed.count("usage_records", world.tenant_id) == 0


async def test_ac7_the_agent_is_denied_at_layer_wall_before_the_delegation_check(
    net: Net, admin: Person, world: World, fake_model: FakeModel
) -> None:
    run_id = await _ready(world)
    agent = await load_agent_context(world.tenant_id, run_id)
    await _wall_requester(net, admin, world)
    resource = Resource.engagement(world.tenant_id, world.engagement_id, archived=False)
    with pytest.raises(Forbidden) as raised:
        await authorise(agent, "evidence.read", resource)
    assert raised.value.layer == "wall"


async def test_ac7_a_run_started_after_the_wall_is_denied_too(
    net: Net, admin: Person, world: World, fake_model: FakeModel
) -> None:
    result = await retrieve(world)
    await _wall_requester(net, admin, world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    agent = await load_agent_context(world.tenant_id, run_id)
    with pytest.raises(Forbidden) as raised:
        await screen(agent)
    assert raised.value.layer == "wall"
    assert await _agent_row(net.seed, run_id) == ("failed", "forbidden")


async def test_ac8_an_agent_for_a_person_walled_from_another_client_completes(
    net: Net, admin: Person, world: World, fake_model: FakeModel
) -> None:
    other = await net.site(world.tenant_id, admin.user_id)
    await net.wall(admin, world.requester.user_id, other.client_id)
    run_id = await _ready(world)
    outcome = await screen(await load_agent_context(world.tenant_id, run_id))
    assert outcome.status == "completed"
    assert await net.seed.count("screening_results", world.tenant_id) == 1


async def test_ac9_after_removal_a_new_screening_run_completes(
    net: Net, admin: Person, world: World, fake_model: FakeModel
) -> None:
    wall_id = await _wall_requester(net, admin, world)
    await net.remove_wall(admin, wall_id)
    run_id = await _ready(world)
    outcome = await screen(await load_agent_context(world.tenant_id, run_id))
    assert outcome.status == "completed"
