"""SPEC-003 AC-6, AC-7, AC-13, AC-14: the slot activities of both workflows (TASK-018 interface
contract 018b, "Activities", and contract revision 1; ADR-071, ADR-017).

The activities run with `ActivityEnvironment` against a real database, with the task queue of the
activity set to a class queue (or not). Slots are blocked by seeding the ledger as the superuser or
by setting the class's caps through `ABACUS_WORK_CLASSES`. Expectations come from the contract, not
the implementation.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from abacus.ai_gateway import FakeModel
from abacus.kernel.config import settings
from abacus.kernel.dispatch import queue_for
from abacus.kernel.slots import LEASE_SECONDS
from abacus.modules.agents import activities as screening
from abacus.modules.agents.workflow_types import FailInput as ScreeningFailInput
from abacus.modules.agents.workflow_types import RunInput, ScreeningInput, SlotGrant
from abacus.modules.connections import activities as retrieval
from abacus.modules.connections.api import start_retrieval
from abacus.modules.connections.workflow_types import FailInput, RetrievalInput
from abacus.modules.connections.workflow_types import SlotGrant as RetrievalGrant

from .support import PERIOD, Seeder, World, retrieve

CLASSES = ("interactive", "time_sensitive", "background", "batch")
RETRIEVAL_STAGES = [
    retrieval.pull_raw_activity,
    retrieval.normalise_raw_activity,
    retrieval.validate_run_activity,
    retrieval.snapshot_activity,
]

CLEAR = {
    "work_slots": "DELETE FROM work_slots",
    "work_waiters": "DELETE FROM work_waiters",
    "work_grants": "DELETE FROM work_grants",
}


@pytest.fixture
def limits(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Override one class's caps (the others keep their defaults); undone after the test."""

    def apply(work_class: str, **caps: int) -> None:
        full = {
            name: {
                "max_activities": 5,
                "max_workflow_tasks": 5,
                "firm_cap": 20,
                "engagement_cap": 10,
                "class_capacity": 50,
                "max_wait_seconds": 120,
            }
            for name in CLASSES
        }
        full[work_class].update(caps)
        monkeypatch.setenv("ABACUS_WORK_CLASSES", json.dumps(full))
        settings.cache_clear()

    yield apply
    monkeypatch.delenv("ABACUS_WORK_CLASSES", raising=False)
    settings.cache_clear()


@pytest.fixture(autouse=True)
async def empty_ledger(seed: Seeder) -> None:
    for table in ("work_slots", "work_waiters", "work_grants"):
        await seed.run(CLEAR[table])


def _env(queue: str, workflow_id: str = "wf", run: str = "run-1") -> ActivityEnvironment:
    env = ActivityEnvironment()
    env.info = dataclasses.replace(
        env.info, task_queue=queue, workflow_id=workflow_id, workflow_run_id=run
    )
    return env


async def _run[T](
    env: ActivityEnvironment, fn: Callable[[T], Awaitable[object]], arg: T
) -> object:
    return await env.run(cast("Callable[[object], Awaitable[object]]", fn), arg)


async def _slot_holders(seed: Seeder, world: World) -> list[str]:
    rows = await seed.rows("SELECT holder FROM work_slots WHERE tenant_id = $1", world.tenant_id)
    return [str(r["holder"]) for r in rows]


async def _block_class(seed: Seeder, work_class: str, count: int = 1) -> None:
    """Slots held by another firm, with a live lease."""
    other = await seed.firm()
    for n in range(count):
        await seed.run(
            "INSERT INTO work_slots (tenant_id, holder, work_class, acquired_at, lease_until) "
            "VALUES ($1, $2, $3, now(), now() + interval '1 hour')",
            other,
            f"blocker-{n}-{uuid.uuid4()}",
            work_class,
        )


async def _block_firm(seed: Seeder, world: World, work_class: str, count: int = 1) -> None:
    for n in range(count):
        await seed.run(
            "INSERT INTO work_slots (tenant_id, holder, work_class, acquired_at, lease_until) "
            "VALUES ($1, $2, $3, now(), now() + interval '1 hour')",
            world.tenant_id,
            f"firm-blocker-{n}-{uuid.uuid4()}",
            work_class,
        )


async def _lease(seed: Seeder, world: World, holder: str) -> datetime:
    return cast(
        datetime,
        await seed.value(
            "SELECT lease_until FROM work_slots WHERE tenant_id = $1 AND holder = $2",
            world.tenant_id,
            holder,
        ),
    )


# =================================================================================================
# retrieval
# =================================================================================================


async def _sync_run(world: World) -> tuple[RetrievalInput, str]:
    started = await start_retrieval(
        world.requester.context(),
        engagement_id=world.engagement_id,
        request_item_id=world.item_id,
        period=PERIOD,
    )
    given = RetrievalInput(str(world.tenant_id), str(started.run_id))
    return given, f"wf-{started.run_id}:run-1"


async def _sync_row(seed: Seeder, run_id: str) -> tuple[str, str | None, datetime | None]:
    [row] = await seed.rows(
        "SELECT status, queued_reason, estimated_start_at FROM sync_runs WHERE id = $1",
        uuid.UUID(run_id),
    )
    return str(row["status"]), row["queued_reason"], row["estimated_start_at"]


def _in_retrieval(given: RetrievalInput, queue: str, run: str = "run-1") -> ActivityEnvironment:
    return _env(queue, f"wf-{given.run_id}", run)


async def _new_events(seed: Seeder, world: World, before: list[str]) -> list[str]:
    return (await seed.actions(world.tenant_id))[len(before) :]


async def test_ac6_acquire_slot_grants_at_once_off_the_class_queues_and_takes_no_slot(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=0)  # would never grant, if it asked
    given, _ = await _sync_run(world)
    before = await seed.actions(world.tenant_id)
    for queue in ("test", "abacus", queue_for("interactive") + "-legacy"):
        grant = await _run(_in_retrieval(given, queue), retrieval.acquire_slot_activity, given)
        assert grant == RetrievalGrant(True, 0)
    assert await _slot_holders(seed, world) == []
    assert await seed.value("SELECT count(*) FROM work_waiters") == 0
    assert await _sync_row(seed, given.run_id) == ("running", None, None)
    assert await _new_events(seed, world, before) == []


@pytest.mark.parametrize("work_class", CLASSES)
async def test_ac6_acquire_slot_takes_a_slot_on_a_class_queue_and_reports_the_max_wait(
    seed: Seeder, world: World, limits: Callable[..., None], work_class: str
) -> None:
    limits(work_class, max_wait_seconds=77)
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for(work_class))  # type: ignore[arg-type]  # test double
    grant = await _run(env, retrieval.acquire_slot_activity, given)
    assert grant == RetrievalGrant(True, 77)
    assert await _slot_holders(seed, world) == [f"wf-{given.run_id}:run-1"]
    assert await _sync_row(seed, given.run_id) == ("running", None, None)


async def test_ac6_acquire_slot_for_an_ended_run_grants_at_once_and_takes_no_slot(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=0)
    given, _ = await _sync_run(world)
    await _run(
        _env("test"),
        retrieval.fail_run_activity,
        FailInput(given.tenant_id, given.run_id, "failed", "cancelled"),
    )
    grant = await _run(
        _in_retrieval(given, queue_for("interactive")), retrieval.acquire_slot_activity, given
    )
    assert grant == RetrievalGrant(True, 0)
    assert await _slot_holders(seed, world) == []
    assert await seed.value("SELECT count(*) FROM work_waiters") == 0


async def test_ac13_acquire_slot_for_a_succeeded_run_grants_at_once(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    result = await retrieve(world)
    limits("interactive", firm_cap=0)
    given = RetrievalInput(str(world.tenant_id), str(result.run_id))
    grant = await _run(
        _in_retrieval(given, queue_for("interactive")), retrieval.acquire_slot_activity, given
    )
    assert grant == RetrievalGrant(True, 0)


async def test_ac13_acquire_slot_marks_the_run_queued_with_the_reason_and_audits_it_once(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=1, max_wait_seconds=30)
    await _block_firm(seed, world, "interactive")
    given, _ = await _sync_run(world)
    before = await seed.actions(world.tenant_id)
    env = _in_retrieval(given, queue_for("interactive"))
    grant = await _run(env, retrieval.acquire_slot_activity, given)
    assert grant == RetrievalGrant(False, 30)
    status, reason, estimate = await _sync_row(seed, given.run_id)
    assert (status, reason, estimate) == ("running", "firm_cap", None)  # no grants: no estimate
    assert await _new_events(seed, world, before) == ["sync_run.queued"]
    for _ in range(3):  # asking again with the same reason writes nothing
        assert await _run(env, retrieval.acquire_slot_activity, given) == RetrievalGrant(False, 30)
    assert await _new_events(seed, world, before) == ["sync_run.queued"]
    assert await _sync_row(seed, given.run_id) == (status, "firm_cap", None)


async def test_ac13_the_queued_audit_event_is_written_by_the_system_for_the_run(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=1)
    await _block_firm(seed, world, "interactive")
    given, _ = await _sync_run(world)
    before = await seed.actions(world.tenant_id)
    await _run(
        _in_retrieval(given, queue_for("interactive")), retrieval.acquire_slot_activity, given
    )
    events = (await seed.events(world.tenant_id))[len(before) :]
    [event] = events
    assert event.action == "sync_run.queued"
    assert event.actor_kind == "system"
    assert event.target_id == given.run_id


async def test_ac13_a_change_of_reason_is_audited_again(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    before = await seed.actions(world.tenant_id)
    limits("interactive", class_capacity=1)
    await _block_class(seed, "interactive")
    await _run(env, retrieval.acquire_slot_activity, given)
    assert (await _sync_row(seed, given.run_id))[1] == "class_capacity"
    limits("interactive", firm_cap=0)  # the firm is paused: a different reason
    await _run(env, retrieval.acquire_slot_activity, given)
    assert (await _sync_row(seed, given.run_id))[1] == "firm_cap"
    assert await _new_events(seed, world, before) == ["sync_run.queued", "sync_run.queued"]


async def test_ac13_a_queued_run_marked_running_again_when_granted_with_resumed_audited_once(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=1)
    blocker = await _block_firm_returning_holder(seed, world)
    given, holder = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    before = await seed.actions(world.tenant_id)
    assert (await _run(env, retrieval.acquire_slot_activity, given)) == RetrievalGrant(False, 120)
    assert (await _sync_row(seed, given.run_id))[1] == "firm_cap"
    await seed.run("DELETE FROM work_slots WHERE holder = $1", blocker)
    assert (await _run(env, retrieval.acquire_slot_activity, given)) == RetrievalGrant(True, 120)
    assert await _sync_row(seed, given.run_id) == ("running", None, None)
    assert await _new_events(seed, world, before) == ["sync_run.queued", "sync_run.resumed"]
    # asking again while holding renews, and writes nothing
    assert (await _run(env, retrieval.acquire_slot_activity, given)) == RetrievalGrant(True, 120)
    assert await _new_events(seed, world, before) == ["sync_run.queued", "sync_run.resumed"]
    assert await _slot_holders(seed, world) == [holder]


async def _block_firm_returning_holder(seed: Seeder, world: World) -> str:
    holder = f"firm-blocker-{uuid.uuid4()}"
    await seed.run(
        "INSERT INTO work_slots (tenant_id, holder, work_class, acquired_at, lease_until) "
        "VALUES ($1, $2, 'interactive', now(), now() + interval '1 hour')",
        world.tenant_id,
        holder,
    )
    return holder


async def test_ac13_a_granted_first_ask_does_not_audit_resumed(seed: Seeder, world: World) -> None:
    given, _ = await _sync_run(world)
    before = await seed.actions(world.tenant_id)
    await _run(
        _in_retrieval(given, queue_for("interactive")), retrieval.acquire_slot_activity, given
    )
    assert await _new_events(seed, world, before) == []


async def test_ac6_acquire_slot_for_an_unknown_run_is_a_non_retryable_not_found(
    world: World,
) -> None:
    given = RetrievalInput(str(world.tenant_id), str(uuid.uuid4()))
    with pytest.raises(ApplicationError) as raised:
        await _run(
            _in_retrieval(given, queue_for("interactive")), retrieval.acquire_slot_activity, given
        )
    assert raised.value.type == "NotFound"
    assert raised.value.non_retryable


async def test_ac6_acquire_slot_trusts_the_run_row_not_the_input_tenant(
    seed: Seeder, world: World
) -> None:
    given, _ = await _sync_run(world)
    other = await seed.firm()
    with pytest.raises(ApplicationError) as raised:
        await _run(
            _in_retrieval(given, queue_for("interactive")),
            retrieval.acquire_slot_activity,
            RetrievalInput(str(other), given.run_id),
        )
    assert raised.value.type == "NotFound"
    assert await seed.value("SELECT count(*) FROM work_slots WHERE tenant_id = $1", other) == 0


async def test_ac6_release_slot_frees_the_slot_and_is_idempotent(
    seed: Seeder, world: World
) -> None:
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    assert len(await _slot_holders(seed, world)) == 1
    assert await _run(env, retrieval.release_slot_activity, given) is None
    assert await _slot_holders(seed, world) == []
    assert await _run(env, retrieval.release_slot_activity, given) is None  # again: nothing


async def test_ac6_release_slot_also_forgets_a_waiting_run(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=1)
    await _block_firm(seed, world, "interactive")
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    assert await seed.value("SELECT count(*) FROM work_waiters") == 1
    await _run(env, retrieval.release_slot_activity, given)
    assert await seed.value("SELECT count(*) FROM work_waiters") == 0


async def test_ac6_release_slot_works_for_a_run_that_has_ended(seed: Seeder, world: World) -> None:
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    await _run(
        env,
        retrieval.fail_run_activity,
        FailInput(given.tenant_id, given.run_id, "failed", "cancelled"),
    )
    await _run(env, retrieval.release_slot_activity, given)
    assert await _slot_holders(seed, world) == []


async def test_ac6_release_slot_is_a_no_op_off_the_class_queues(
    seed: Seeder, world: World
) -> None:
    given, _ = await _sync_run(world)
    holder = f"wf-{given.run_id}:run-1"
    await _run(
        _in_retrieval(given, queue_for("interactive")), retrieval.acquire_slot_activity, given
    )
    assert await _run(_in_retrieval(given, "test"), retrieval.release_slot_activity, given) is None
    assert await _slot_holders(seed, world) == [holder]  # untouched: it was not that queue's


async def test_ac6_release_only_frees_the_run_of_its_own_workflow_execution(
    seed: Seeder, world: World
) -> None:
    given, _ = await _sync_run(world)
    first = _in_retrieval(given, queue_for("interactive"), "run-1")
    second = _in_retrieval(given, queue_for("interactive"), "run-2")
    await _run(first, retrieval.acquire_slot_activity, given)
    await _run(second, retrieval.acquire_slot_activity, given)
    assert len(await _slot_holders(seed, world)) == 2
    await _run(first, retrieval.release_slot_activity, given)
    assert await _slot_holders(seed, world) == [f"wf-{given.run_id}:run-2"]


@pytest.mark.parametrize("index", range(len(RETRIEVAL_STAGES)))
async def test_ac6_every_retrieval_stage_renews_the_slot_first(
    seed: Seeder, world: World, index: int
) -> None:
    given, holder = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    for earlier in RETRIEVAL_STAGES[:index]:
        await _run(env, earlier, given)
    await seed.run("UPDATE work_slots SET lease_until = now() + interval '5 seconds'")
    await _run(env, RETRIEVAL_STAGES[index], given)
    assert await _lease(seed, world, holder) > datetime.now(UTC) + timedelta(
        seconds=LEASE_SECONDS - 60
    )


async def test_ac6_the_render_stage_renews_the_slot_too(seed: Seeder, world: World) -> None:
    given, holder = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    for stage in RETRIEVAL_STAGES:
        await _run(env, stage, given)
    await seed.run("UPDATE work_slots SET lease_until = now() + interval '5 seconds'")
    await _run(env, retrieval.render_activity, given)
    assert await _lease(seed, world, holder) > datetime.now(UTC) + timedelta(minutes=10)


async def test_ac6_a_stage_off_the_class_queues_touches_no_slot(
    seed: Seeder, world: World
) -> None:
    given, _ = await _sync_run(world)
    await _run(_env("test"), retrieval.pull_raw_activity, given)
    assert await seed.value("SELECT count(*) FROM work_slots") == 0


async def test_ac6_a_stage_takes_a_slot_again_when_the_lease_was_reclaimed(
    seed: Seeder, world: World
) -> None:
    given, holder = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    await seed.run("DELETE FROM work_slots")  # reclaimed after a long outage
    await _run(env, retrieval.pull_raw_activity, given)
    assert await _slot_holders(seed, world) == [holder]


async def test_ac6_a_stage_still_runs_when_no_slot_is_free_after_a_reclaim(
    seed: Seeder,
    world: World,
    limits: Callable[..., None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    await seed.run("DELETE FROM work_slots")
    limits("interactive", class_capacity=1)
    await _block_class(seed, "interactive")
    capsys.readouterr()
    await _run(env, retrieval.pull_raw_activity, given)  # does not raise
    assert await _slot_holders(seed, world) == []
    out = capsys.readouterr()
    lines = [
        cast("dict[str, object]", json.loads(line))
        for line in (out.out + out.err).splitlines()
        if line.strip().startswith("{")
    ]
    [lost] = [e for e in lines if e.get("event") == "slot.lost"]
    assert lost["level"] == "warning"
    assert lost["tenant_id"] == str(world.tenant_id)


# --- a run that ends clears its queued fields ----------------------------------------------------


async def test_ac14_a_queued_run_failed_capacity_timeout_ends_cleanly_and_clears_the_queue_fields(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=1)
    await _block_firm(seed, world, "interactive")
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    assert (await _sync_row(seed, given.run_id))[1] == "firm_cap"
    outcome = await _run(
        env,
        retrieval.fail_run_activity,
        FailInput(given.tenant_id, given.run_id, "failed", "capacity_timeout"),
    )
    assert (outcome.status, outcome.code) == ("failed", "capacity_timeout")  # type: ignore[attr-defined]  # test double
    assert await _sync_row(seed, given.run_id) == ("failed", None, None)
    [row] = await seed.rows(
        "SELECT failure_code, finished_at FROM sync_runs WHERE id = $1", uuid.UUID(given.run_id)
    )
    assert row["failure_code"] == "capacity_timeout"
    assert row["finished_at"] is not None
    assert "sync_run.failed" in await seed.actions(world.tenant_id)


async def test_ac14_a_queued_run_cancelled_ends_cleanly(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("interactive", firm_cap=1)
    await _block_firm(seed, world, "interactive")
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    await _run(env, retrieval.acquire_slot_activity, given)
    await _run(
        env,
        retrieval.fail_run_activity,
        FailInput(given.tenant_id, given.run_id, "failed", "cancelled"),
    )
    assert await _sync_row(seed, given.run_id) == ("failed", None, None)


async def test_ac13_a_queued_run_that_succeeds_later_has_no_queue_fields(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    # queued first, then granted, then run to the end
    await seed.run(
        "UPDATE sync_runs SET queued_reason = 'class_capacity', estimated_start_at = now() "
        "WHERE id = $1",
        uuid.UUID(given.run_id),
    )
    await _run(env, retrieval.acquire_slot_activity, given)
    assert await _sync_row(seed, given.run_id) == ("running", None, None)
    for stage in RETRIEVAL_STAGES:
        await _run(env, stage, given)
    await _run(env, retrieval.render_activity, given)
    assert await _sync_row(seed, given.run_id) == ("succeeded", None, None)


async def test_ac13_a_run_with_queue_fields_set_that_succeeds_clears_them(
    seed: Seeder, world: World
) -> None:
    given, _ = await _sync_run(world)
    env = _in_retrieval(given, queue_for("interactive"))
    for stage in RETRIEVAL_STAGES:
        await _run(env, stage, given)
    await seed.run(
        "UPDATE sync_runs SET queued_reason = 'deferred', estimated_start_at = now() "
        "WHERE id = $1",
        uuid.UUID(given.run_id),
    )
    await _run(env, retrieval.render_activity, given)
    assert await _sync_row(seed, given.run_id) == ("succeeded", None, None)


# =================================================================================================
# screening
# =================================================================================================


async def _agent_run(world: World) -> RunInput:
    result = await retrieve(world)
    made = await _run(
        _env("test"),
        screening.create_run_activity,
        ScreeningInput(
            str(world.tenant_id),
            str(result.evidence_version_id),
            str(uuid.uuid4()),
            str(world.requester.user_id),
        ),
    )
    assert isinstance(made, str)
    return RunInput(str(world.tenant_id), made)


def _in_screening(given: RunInput, queue: str, run: str = "run-1") -> ActivityEnvironment:
    return _env(queue, f"screening-{given.run_id}", run)


async def _agent_row(seed: Seeder, run_id: str) -> tuple[str, str | None, datetime | None]:
    [row] = await seed.rows(
        "SELECT status, queued_reason, estimated_start_at FROM agent_runs WHERE id = $1",
        uuid.UUID(run_id),
    )
    return str(row["status"]), row["queued_reason"], row["estimated_start_at"]


async def test_ac6_screening_acquire_slot_grants_at_once_off_the_class_queues(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("time_sensitive", firm_cap=0)
    given = await _agent_run(world)
    before = await seed.actions(world.tenant_id)
    for queue in ("test", "abacus"):
        grant = await _run(_in_screening(given, queue), screening.acquire_slot_activity, given)
        assert grant == SlotGrant(True, 0)
    assert await _slot_holders(seed, world) == []
    assert await _new_events(seed, world, before) == []
    assert await _agent_row(seed, given.run_id) == ("running", None, None)


async def test_ac6_screening_acquire_slot_takes_a_time_sensitive_slot(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("time_sensitive", max_wait_seconds=91)
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    assert await _run(env, screening.acquire_slot_activity, given) == SlotGrant(True, 91)
    assert await _slot_holders(seed, world) == [f"screening-{given.run_id}:run-1"]
    assert await seed.value("SELECT work_class FROM work_slots") == "time_sensitive"


async def test_ac6_screening_acquire_slot_for_an_ended_run_grants_at_once(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    given = await _agent_run(world)
    await _run(
        _env("test"),
        screening.fail_run_activity,
        ScreeningFailInput(given.tenant_id, given.run_id, "cancelled"),
    )
    limits("time_sensitive", firm_cap=0)
    grant = await _run(
        _in_screening(given, queue_for("time_sensitive")), screening.acquire_slot_activity, given
    )
    assert grant == SlotGrant(True, 0)
    assert await _slot_holders(seed, world) == []


async def test_ac13_screening_marks_queued_and_resumed_and_audits_only_on_change(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("time_sensitive", firm_cap=1, max_wait_seconds=600)
    blocker = f"firm-blocker-{uuid.uuid4()}"
    await seed.run(
        "INSERT INTO work_slots (tenant_id, holder, work_class, acquired_at, lease_until) "
        "VALUES ($1, $2, 'time_sensitive', now(), now() + interval '1 hour')",
        world.tenant_id,
        blocker,
    )
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    before = await seed.actions(world.tenant_id)
    for _ in range(3):
        assert await _run(env, screening.acquire_slot_activity, given) == SlotGrant(False, 600)
    status, reason, _estimate = await _agent_row(seed, given.run_id)
    assert (status, reason) == ("running", "firm_cap")
    assert await _new_events(seed, world, before) == ["agent_run.queued"]
    await seed.run("DELETE FROM work_slots WHERE holder = $1", blocker)
    assert await _run(env, screening.acquire_slot_activity, given) == SlotGrant(True, 600)
    assert await _agent_row(seed, given.run_id) == ("running", None, None)
    assert await _run(env, screening.acquire_slot_activity, given) == SlotGrant(True, 600)
    assert await _new_events(seed, world, before) == ["agent_run.queued", "agent_run.resumed"]


async def test_ac13_screening_audit_events_are_the_systems_for_the_run(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("time_sensitive", firm_cap=1)
    await _block_firm(seed, world, "time_sensitive")
    given = await _agent_run(world)
    before = await seed.actions(world.tenant_id)
    await _run(
        _in_screening(given, queue_for("time_sensitive")), screening.acquire_slot_activity, given
    )
    [event] = (await seed.events(world.tenant_id))[len(before) :]
    assert event.action == "agent_run.queued"
    assert event.target_id == given.run_id


async def test_ac6_screening_acquire_slot_for_an_unknown_run_is_a_non_retryable_not_found(
    world: World,
) -> None:
    given = RunInput(str(world.tenant_id), str(uuid.uuid4()))
    with pytest.raises(ApplicationError) as raised:
        await _run(
            _in_screening(given, queue_for("time_sensitive")),
            screening.acquire_slot_activity,
            given,
        )
    assert raised.value.type == "NotFound"
    assert raised.value.non_retryable


async def test_ac6_screening_release_slot_frees_it_and_is_a_no_op_off_the_class_queues(
    seed: Seeder, world: World
) -> None:
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    await _run(env, screening.acquire_slot_activity, given)
    assert await _run(_in_screening(given, "test"), screening.release_slot_activity, given) is None
    assert len(await _slot_holders(seed, world)) == 1
    assert await _run(env, screening.release_slot_activity, given) is None
    assert await _slot_holders(seed, world) == []
    assert await _run(env, screening.release_slot_activity, given) is None


async def test_ac6_screening_screen_renews_the_slot_first(
    seed: Seeder, world: World, fake_model: FakeModel
) -> None:
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    await _run(env, screening.acquire_slot_activity, given)
    await seed.run("UPDATE work_slots SET lease_until = now() + interval '5 seconds'")
    outcome = await _run(env, screening.screen_activity, given)
    assert outcome.status == "completed"  # type: ignore[attr-defined]  # test double
    assert await _lease(seed, world, f"screening-{given.run_id}:run-1") > datetime.now(
        UTC
    ) + timedelta(minutes=10)


async def test_ac6_screening_screen_takes_a_slot_again_when_the_lease_was_reclaimed(
    seed: Seeder, world: World, fake_model: FakeModel
) -> None:
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    await _run(env, screening.acquire_slot_activity, given)
    await seed.run("DELETE FROM work_slots")
    await _run(env, screening.screen_activity, given)
    assert await _slot_holders(seed, world) == [f"screening-{given.run_id}:run-1"]


async def test_ac6_screening_screen_off_the_class_queues_touches_no_slot(
    seed: Seeder, world: World, fake_model: FakeModel
) -> None:
    given = await _agent_run(world)
    await _run(_env("test"), screening.screen_activity, given)
    assert await seed.value("SELECT count(*) FROM work_slots") == 0


async def test_ac14_a_queued_screening_run_failed_capacity_timeout_ends_cleanly(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("time_sensitive", firm_cap=1)
    await _block_firm(seed, world, "time_sensitive")
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    await _run(env, screening.acquire_slot_activity, given)
    assert (await _agent_row(seed, given.run_id))[1] == "firm_cap"
    outcome = await _run(
        env,
        screening.fail_run_activity,
        ScreeningFailInput(given.tenant_id, given.run_id, "capacity_timeout"),
    )
    assert (outcome.status, outcome.code) == ("failed", "capacity_timeout")  # type: ignore[attr-defined]  # test double
    assert await _agent_row(seed, given.run_id) == ("failed", None, None)
    [row] = await seed.rows(
        "SELECT failure_code FROM agent_runs WHERE id = $1", uuid.UUID(given.run_id)
    )
    assert row["failure_code"] == "capacity_timeout"


async def test_ac14_a_queued_screening_run_cancelled_ends_cleanly(
    seed: Seeder, world: World, limits: Callable[..., None]
) -> None:
    limits("time_sensitive", firm_cap=1)
    await _block_firm(seed, world, "time_sensitive")
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    await _run(env, screening.acquire_slot_activity, given)
    await _run(
        env,
        screening.fail_run_activity,
        ScreeningFailInput(given.tenant_id, given.run_id, "cancelled"),
    )
    assert await _agent_row(seed, given.run_id) == ("failed", None, None)


async def test_ac13_a_queued_screening_run_that_completes_has_no_queue_fields(
    seed: Seeder, world: World, fake_model: FakeModel
) -> None:
    given = await _agent_run(world)
    env = _in_screening(given, queue_for("time_sensitive"))
    await seed.run(
        "UPDATE agent_runs SET queued_reason = 'class_capacity', estimated_start_at = now() "
        "WHERE id = $1",
        uuid.UUID(given.run_id),
    )
    await _run(env, screening.acquire_slot_activity, given)
    await _run(env, screening.screen_activity, given)
    assert await _agent_row(seed, given.run_id) == ("completed", None, None)
