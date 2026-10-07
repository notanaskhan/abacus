"""SPEC-003 AC-6, AC-8, AC-13, AC-15: `abacus.kernel.slots` (TASK-018 interface contract 018b,
"`abacus.kernel.slots`", and contract revision 1; ADR-071).

The database is replaced by a fake connection that records the statements and answers from a
script, so these tests pin what the module passes through (the settings' caps, the lease), what it
counts and logs, and how `keep`, `current_holder` and `current_class` behave. The functions
themselves are tested against Postgres in `tests/integration/agent_tests/test_work_slots_db.py`.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricsData
from opentelemetry.sdk.metrics.export import Sum as SumData
from temporalio.testing import ActivityEnvironment

from abacus.kernel import slots
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import queue_for
from abacus.kernel.slots import (
    LEASE_SECONDS,
    SLOT_DECISIONS,
    SlotDecision,
    acquire,
    current_class,
    current_holder,
    keep,
    release,
    renew,
    system_tenant,
)

TENANT = uuid.UUID(int=7)
ENGAGEMENT = uuid.UUID(int=8)
CTX = TenantContext(TENANT, "system", "work-slots")
SOON = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
CLASSES = ("interactive", "time_sensitive", "background", "batch")


class Row(tuple[Any, ...]):  # a recorded call
    def one(self) -> Row:
        return self


class Fake:
    """A connection that records `(sql, params)` and a commit count, and answers from a script."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, dict[str, object]]] = []
        self.commits = 0
        self.contexts: list[TenantContext] = []
        self.row: tuple[object, ...] = (True, None, None)
        self.scalar_value: object = True

    async def execute(self, statement: object, params: dict[str, object] | None = None) -> Row:
        self.statements.append((str(statement), params or {}))
        return Row(self.row)

    async def scalar(self, statement: object, params: dict[str, object] | None = None) -> object:
        self.statements.append((str(statement), params or {}))
        return self.scalar_value

    async def commit(self) -> None:
        self.commits += 1

    @property
    def functions(self) -> list[str]:
        return [sql for sql, _ in self.statements]


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Fake:
    fake = Fake()

    @asynccontextmanager
    async def connection(ctx: TenantContext) -> AsyncGenerator[Fake]:
        fake.contexts.append(ctx)
        yield fake

    monkeypatch.setattr(slots, "tenant_connection", connection)
    return fake


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemoryMetricReader]:
    """The decisions counter on a provider of its own, with the platform's attribute view."""
    from opentelemetry.sdk.metrics.view import View

    reader = InMemoryMetricReader()
    provider = MeterProvider(
        metric_readers=[reader],
        views=[
            View(
                instrument_name="*",
                attribute_keys={"work_class", "provider", "model", "reason", "outcome"},
            )
        ],
    )
    monkeypatch.setattr(
        slots, "_decisions", provider.get_meter("test").create_counter(SLOT_DECISIONS)
    )
    yield reader
    provider.shutdown()


def _points(reader: InMemoryMetricReader) -> list[tuple[dict[str, object], object]]:
    data: MetricsData | None = reader.get_metrics_data()
    found: list[tuple[dict[str, object], object]] = []
    if data is None:
        return found
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name == SLOT_DECISIONS and isinstance(metric.data, SumData):
                    for point in metric.data.data_points:
                        found.append((dict(point.attributes or {}), point.value))
    return found


def _log_lines(captured: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    out = captured.readouterr()
    return [
        cast("dict[str, object]", json.loads(line))
        for line in (out.out + out.err).splitlines()
        if line.strip().startswith("{")
    ]


# --- constants -----------------------------------------------------------------------------------


def test_ac6_the_lease_is_fifteen_minutes_and_the_counter_is_named_in_the_contract() -> None:
    assert LEASE_SECONDS == 900
    assert SLOT_DECISIONS == "abacus.slots.decisions"


def test_ac6_a_decision_is_granted_or_a_reason_and_an_estimate() -> None:
    decision = SlotDecision(False, "firm_cap", SOON)
    assert (decision.granted, decision.reason, decision.estimated_start_at) == (
        False,
        "firm_cap",
        SOON,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.granted = True  # type: ignore[misc]  # test double


def test_ac6_the_settings_hold_the_documented_caps_for_every_class() -> None:
    table = {
        "interactive": (20, 10, 50, 120),
        "time_sensitive": (20, 10, 50, 600),
        "background": (10, 5, 20, 21_600),
        "batch": (5, 2, 10, 86_400),
    }
    for name, (firm, engagement, capacity, wait) in table.items():
        limits = settings().work_classes[name]  # type: ignore[index]  # test double
        assert (limits.firm_cap, limits.engagement_cap) == (firm, engagement)
        assert (limits.class_capacity, limits.max_wait_seconds) == (capacity, wait)


# --- acquire: settings caps pass through ---------------------------------------------------------


@pytest.mark.parametrize("work_class", CLASSES)
async def test_ac6_acquire_passes_the_classes_settings_caps_and_the_lease(
    db: Fake, work_class: str
) -> None:
    limits = settings().work_classes[work_class]  # type: ignore[index]  # test double
    await acquire(CTX, "wf:run", ENGAGEMENT, work_class)  # type: ignore[arg-type]  # test double
    [(sql, params)] = db.statements
    assert "work_slot_acquire" in sql
    assert params == {
        "holder": "wf:run",
        "engagement_id": ENGAGEMENT,
        "work_class": work_class,
        "firm_cap": limits.firm_cap,
        "engagement_cap": limits.engagement_cap,
        "class_capacity": limits.class_capacity,
        "lease_seconds": LEASE_SECONDS,
    }


async def test_ac6_acquire_uses_the_configured_limits_not_the_defaults(
    db: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = {
        c: {
            "max_activities": 1,
            "max_workflow_tasks": 1,
            "firm_cap": 3,
            "engagement_cap": 2,
            "class_capacity": 4,
            "max_wait_seconds": 5,
            "admission_reserve_pct": 0,
        }
        for c in CLASSES
    }
    monkeypatch.setenv("ABACUS_WORK_CLASSES", json.dumps(custom))
    settings.cache_clear()
    try:
        await acquire(CTX, "h", None, "batch")
    finally:
        monkeypatch.undo()
        settings.cache_clear()
    [(_, params)] = db.statements
    assert (params["firm_cap"], params["engagement_cap"], params["class_capacity"]) == (3, 2, 4)


async def test_ac6_acquire_runs_for_the_given_tenant_and_commits_on_its_own(db: Fake) -> None:
    await acquire(CTX, "h", None, "interactive")
    assert db.contexts == [CTX]
    assert db.commits == 1


async def test_ac6_acquire_returns_the_functions_decision(db: Fake) -> None:
    db.row = (False, "engagement_cap", SOON)
    assert await acquire(CTX, "h", ENGAGEMENT, "background") == SlotDecision(
        False, "engagement_cap", SOON
    )
    db.row = (True, None, None)
    assert await acquire(CTX, "h", ENGAGEMENT, "background") == SlotDecision(True, None, None)


# --- the decisions counter and the logs ----------------------------------------------------------


async def test_ac15_a_granted_acquire_counts_granted_and_logs_slot_acquired(
    db: Fake, counter: InMemoryMetricReader, capsys: pytest.CaptureFixture[str]
) -> None:
    await acquire(CTX, "holder-1", None, "interactive")
    assert _points(counter) == [
        ({"work_class": "interactive", "outcome": "granted", "reason": ""}, 1)
    ]
    [line] = [e for e in _log_lines(capsys) if e.get("event") == "slot.acquired"]
    assert line["tenant_id"] == str(TENANT)
    assert line["work_class"] == "interactive"


@pytest.mark.parametrize("reason", ["firm_cap", "engagement_cap", "class_capacity"])
async def test_ac13_a_waiting_acquire_counts_waiting_with_the_reason_and_logs_slot_waiting(
    db: Fake, counter: InMemoryMetricReader, capsys: pytest.CaptureFixture[str], reason: str
) -> None:
    db.row = (False, reason, None)
    await acquire(CTX, "holder-2", None, "batch")
    assert _points(counter) == [
        ({"work_class": "batch", "outcome": "waiting", "reason": reason}, 1)
    ]
    [line] = [e for e in _log_lines(capsys) if e.get("event") == "slot.waiting"]
    assert (line["tenant_id"], line["work_class"], line["reason"]) == (
        str(TENANT),
        "batch",
        reason,
    )


async def test_ac15_every_acquire_increments_the_counter(
    db: Fake, counter: InMemoryMetricReader
) -> None:
    for _ in range(3):
        await acquire(CTX, "h", None, "interactive")
    db.row = (False, "firm_cap", None)
    await acquire(CTX, "h", None, "interactive")
    points = dict((tuple(sorted(a.items())), v) for a, v in _points(counter))
    assert sum(cast(int, v) for v in points.values()) == 4
    assert points[(("outcome", "granted"), ("reason", ""), ("work_class", "interactive"))] == 3


async def test_ac15_the_logs_and_counter_carry_identifiers_only(
    db: Fake, counter: InMemoryMetricReader, capsys: pytest.CaptureFixture[str]
) -> None:
    db.row = (False, "firm_cap", SOON)
    await acquire(CTX, "workflow-id-with-client-name:run", ENGAGEMENT, "interactive")
    lines = [e for e in _log_lines(capsys) if str(e.get("event", "")).startswith("slot.")]
    assert lines
    for entry in lines:
        text = json.dumps(entry)
        assert "client-name" not in text  # the holder (a workflow ID) is not logged
        assert str(ENGAGEMENT) not in text
    for attributes, _ in _points(counter):
        assert set(attributes) <= {"work_class", "outcome", "reason"}


async def test_ac15_renew_and_release_do_not_count_as_decisions(
    db: Fake, counter: InMemoryMetricReader
) -> None:
    await renew(CTX, "h")
    await release(TENANT, "h")
    assert _points(counter) == []


# --- renew and release ---------------------------------------------------------------------------


@pytest.mark.parametrize("answer", [True, False])
async def test_ac6_renew_passes_the_lease_and_returns_whether_the_holder_held_a_slot(
    db: Fake, answer: bool
) -> None:
    db.scalar_value = answer
    assert await renew(CTX, "wf:run") is answer
    [(sql, params)] = db.statements
    assert "work_slot_renew" in sql
    assert params == {"holder": "wf:run", "lease_seconds": LEASE_SECONDS}
    assert db.commits == 1
    assert db.contexts == [CTX]


async def test_ac6_release_needs_only_the_firm_and_commits_on_its_own(db: Fake) -> None:
    assert await release(TENANT, "wf:run") is None
    [(sql, params)] = db.statements
    assert "work_slot_release" in sql
    assert params == {"holder": "wf:run"}
    assert db.commits == 1
    assert db.contexts == [system_tenant(TENANT)]


def test_ac6_the_system_tenant_is_the_firms_slot_context() -> None:
    assert system_tenant(TENANT) == TenantContext(TENANT, "system", "work-slots")


# --- inside an activity: current_holder, current_class -------------------------------------------


def _env(
    queue: str, workflow_id: str = "retrieval:abc", run_id: str = "run-1"
) -> ActivityEnvironment:
    env = ActivityEnvironment()
    env.info = dataclasses.replace(
        env.info, task_queue=queue, workflow_id=workflow_id, workflow_run_id=run_id
    )
    return env


def test_ac6_the_holder_is_the_workflow_id_and_run_id() -> None:
    assert _env(queue_for("interactive")).run(current_holder) == "retrieval:abc:run-1"


def test_ac6_a_new_run_of_the_same_workflow_id_is_a_different_holder() -> None:
    first = _env("q", "wf", "run-1").run(current_holder)
    second = _env("q", "wf", "run-2").run(current_holder)
    assert first != second


@pytest.mark.parametrize("work_class", CLASSES)
def test_ac6_the_class_is_that_of_the_activitys_task_queue(work_class: str) -> None:
    assert _env(queue_for(work_class)).run(current_class) == work_class  # type: ignore[arg-type]  # test double


@pytest.mark.parametrize("queue", ["abacus", "abacus-unknown", "other-interactive", ""])
def test_ac6_the_class_is_none_off_the_class_queues(queue: str) -> None:
    assert _env(queue).run(current_class) is None


def test_ac6_the_class_follows_the_configured_base_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", "custom-base")
    settings.cache_clear()
    try:
        assert _env("custom-base-batch").run(current_class) == "batch"
        assert _env("abacus-batch").run(current_class) is None
    finally:
        monkeypatch.undo()
        settings.cache_clear()


# --- keep: renew, re-acquire, slot.lost ----------------------------------------------------------


class Script:
    """Replaces `renew` and `acquire`, recording the calls."""

    def __init__(self, renewed: bool, granted: bool = True) -> None:
        self.renewed, self.granted = renewed, granted
        self.calls: list[str] = []

    async def renew(self, tenant: TenantContext, holder: str) -> bool:
        self.calls.append(f"renew:{holder}")
        return self.renewed

    async def acquire(
        self, tenant: TenantContext, holder: str, engagement_id: uuid.UUID | None, work_class: str
    ) -> SlotDecision:
        self.calls.append(f"acquire:{holder}:{engagement_id}:{work_class}")
        return SlotDecision(self.granted, None if self.granted else "class_capacity", None)


def _script(monkeypatch: pytest.MonkeyPatch, **kwargs: bool) -> Script:
    script = Script(**kwargs)
    monkeypatch.setattr(slots, "renew", script.renew)
    monkeypatch.setattr(slots, "acquire", script.acquire)
    return script


async def _keep_in_activity() -> None:
    await keep(CTX, ENGAGEMENT, "interactive")


async def test_ac6_keep_only_renews_while_the_lease_is_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _script(monkeypatch, renewed=True)
    await _env(queue_for("interactive")).run(_keep_in_activity)
    assert script.calls == ["renew:retrieval:abc:run-1"]


async def test_ac6_keep_takes_a_slot_again_when_the_lease_was_reclaimed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _script(monkeypatch, renewed=False, granted=True)
    await _env(queue_for("interactive")).run(_keep_in_activity)
    assert script.calls == [
        "renew:retrieval:abc:run-1",
        f"acquire:retrieval:abc:run-1:{ENGAGEMENT}:interactive",
    ]
    assert not [e for e in _log_lines(capsys) if e.get("event") == "slot.lost"]


async def test_ac6_keep_lets_the_stage_run_and_logs_slot_lost_when_no_slot_is_free(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _script(monkeypatch, renewed=False, granted=False)
    await _env(queue_for("interactive")).run(_keep_in_activity)  # does not raise
    [line] = [e for e in _log_lines(capsys) if e.get("event") == "slot.lost"]
    assert line["level"] == "warning"
    assert (line["tenant_id"], line["work_class"]) == (str(TENANT), "interactive")
