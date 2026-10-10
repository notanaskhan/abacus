"""AC-1, AC-2, AC-4: work classes, queue names, registration and `dispatch` (TASK-018 interface
contract, "abacus.kernel.dispatch" and "Registrations"; SPEC-003; ADR-071).

The workflow registry is process-wide, so each test registers its own throwaway workflow types.
`dispatch` is driven with a fake Temporal client (`configure_temporal_client`).
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Iterator
from datetime import timedelta
from typing import cast, get_args

import pytest
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.config import settings
from abacus.kernel.dispatch import (
    WORK_CLASSES,
    WorkClass,
    dispatch,
    queue_for,
    register_work_classes,
    work_class_of,
    work_class_of_queue,
)
from abacus.kernel.temporal import configure_temporal_client
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections

CLASSES = ("interactive", "time_sensitive", "background", "batch")
QUEUES = {
    "interactive": "abacus-interactive",
    "time_sensitive": "abacus-time-sensitive",
    "background": "abacus-background",
    "batch": "abacus-batch",
}


class Recorder:
    """Stands in for the Temporal client: records starts, or fails them."""

    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def start_workflow(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))
        if self.failure is not None:
            raise self.failure


@pytest.fixture
def client() -> Iterator[Recorder]:
    recorder = Recorder()
    configure_temporal_client(cast(Client, recorder))
    yield recorder
    configure_temporal_client(None)


def _workflow(name: str) -> type:
    async def run(self: object, arg: object) -> None:
        return None

    return type(name, (), {"run": run})


# --- the classes and their queues ----------------------------------------------------------------


def test_ac1_there_are_four_work_classes_in_priority_order() -> None:
    assert WORK_CLASSES == CLASSES
    assert get_args(WorkClass) == CLASSES


@pytest.mark.parametrize("work_class", CLASSES)
def test_ac1_each_class_has_its_own_queue_named_after_the_base(work_class: WorkClass) -> None:
    assert queue_for(work_class) == QUEUES[work_class]


def test_ac1_the_four_queues_are_distinct() -> None:
    assert len({queue_for(c) for c in WORK_CLASSES}) == 4


def test_ac1_queue_names_follow_the_configured_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", "custom")
    settings.cache_clear()
    try:
        assert [queue_for(c) for c in WORK_CLASSES] == [
            "custom-interactive",
            "custom-time-sensitive",
            "custom-background",
            "custom-batch",
        ]
    finally:
        monkeypatch.undo()
        settings.cache_clear()


@pytest.mark.parametrize("unknown", ["", "urgent", "time-sensitive", "INTERACTIVE", "legacy"])
def test_ac1_an_unknown_class_has_no_queue(unknown: str) -> None:
    with pytest.raises(ValueError):
        queue_for(cast(WorkClass, unknown))


# --- registration (AC-4) -------------------------------------------------------------------------


@pytest.mark.parametrize("work_class", CLASSES)
def test_ac4_a_workflow_with_a_class_is_registered(work_class: WorkClass) -> None:
    flow = _workflow("Registered")
    register_work_classes({flow: work_class})
    assert work_class_of(flow) == work_class


def test_ac4_several_workflows_register_at_once() -> None:
    first, second = _workflow("First"), _workflow("Second")
    register_work_classes({first: "batch", second: "interactive"})
    assert (work_class_of(first), work_class_of(second)) == ("batch", "interactive")


def test_ac4_a_workflow_that_was_never_registered_has_no_class() -> None:
    with pytest.raises(LookupError):
        work_class_of(_workflow("Unregistered"))


@pytest.mark.parametrize("unknown", ["", "urgent", "time-sensitive", "INTERACTIVE"])
def test_ac4_registering_an_unknown_class_raises(unknown: str) -> None:
    flow = _workflow("Unknown")
    with pytest.raises(ValueError):
        register_work_classes({flow: cast("WorkClass", unknown)})
    with pytest.raises(LookupError):  # and nothing was registered
        work_class_of(flow)


def test_ac4_registering_the_same_class_again_is_a_no_op() -> None:
    flow = _workflow("Again")
    register_work_classes({flow: "background"})
    register_work_classes({flow: "background"})
    assert work_class_of(flow) == "background"


def test_ac4_registering_another_class_raises_and_keeps_the_first() -> None:
    flow = _workflow("Conflicting")
    register_work_classes({flow: "background"})
    with pytest.raises(ValueError):
        register_work_classes({flow: "interactive"})
    assert work_class_of(flow) == "background"


def test_ac4_an_empty_registration_does_nothing() -> None:
    register_work_classes({})


# --- registrations (SPEC-003 Q1) -----------------------------------------------------------------


def test_ac2_retrieval_is_interactive() -> None:
    assert {connections.RetrievalWorkflow: "interactive"} == connections.WORKFLOWS
    assert work_class_of(connections.RetrievalWorkflow) == "interactive"


def test_ac2_screening_is_time_sensitive_as_its_spec_says() -> None:
    assert agents.WORKFLOWS[agents.ScreeningWorkflow] == "time_sensitive"
    # SPEC-009: knowledge embedding is batch work; SPEC-027: the engagement agent is background.
    assert [c for w, c in agents.WORKFLOWS.items() if w is not agents.ScreeningWorkflow] == [
        "batch",
        "background",
    ]
    assert agents.spec(agents.SCREENER).work_class == "time_sensitive"
    assert work_class_of(agents.ScreeningWorkflow) == "time_sensitive"


# --- dispatch (AC-2) -----------------------------------------------------------------------------


@pytest.mark.parametrize("work_class", CLASSES)
async def test_ac2_dispatch_starts_the_workflow_on_its_class_queue(
    client: Recorder, work_class: WorkClass
) -> None:
    flow = _workflow("Dispatched")
    register_work_classes({flow: work_class})
    await dispatch(
        flow,
        "the-input",
        id="wf-1",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    [(args, kwargs)] = client.calls
    assert args == (vars(flow)["run"], "the-input")
    assert kwargs["id"] == "wf-1"
    assert kwargs["task_queue"] == QUEUES[work_class]
    assert kwargs["id_reuse_policy"] == WorkflowIDReusePolicy.ALLOW_DUPLICATE
    assert kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.USE_EXISTING
    assert kwargs["execution_timeout"] is None


async def test_ac2_dispatch_passes_the_policies_and_the_execution_timeout_through(
    client: Recorder,
) -> None:
    flow = _workflow("Policies")
    register_work_classes({flow: "time_sensitive"})
    await dispatch(
        flow,
        {"k": "v"},
        id="wf-2",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        execution_timeout=timedelta(hours=6),
    )
    [(_, kwargs)] = client.calls
    assert kwargs["id_reuse_policy"] == WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
    assert kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.FAIL
    assert kwargs["execution_timeout"] == timedelta(hours=6)
    assert kwargs["task_queue"] == "abacus-time-sensitive"


async def test_ac2_dispatch_follows_the_configured_base_queue(
    client: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    flow = _workflow("Based")
    register_work_classes({flow: "batch"})
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", "elsewhere")
    settings.cache_clear()
    try:
        await dispatch(
            flow,
            "x",
            id="wf-3",
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
    finally:
        monkeypatch.undo()
        settings.cache_clear()
    [(_, kwargs)] = client.calls
    assert kwargs["task_queue"] == "elsewhere-batch"


async def test_ac4_dispatching_an_unregistered_workflow_raises_before_contacting_temporal(
    client: Recorder,
) -> None:
    with pytest.raises(LookupError):
        await dispatch(
            _workflow("Nobody"),
            "x",
            id="wf-4",
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
    assert client.calls == []


async def test_ac4_an_unregistered_workflow_never_asks_for_the_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_temporal_client(None)
    monkeypatch.delenv("ABACUS_TEMPORAL_TARGET", raising=False)
    settings.cache_clear()
    try:
        with pytest.raises(LookupError):  # not the "temporal_target is not configured" error
            await dispatch(
                _workflow("NobodyAtAll"),
                "x",
                id="wf-5",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
    finally:
        monkeypatch.undo()
        settings.cache_clear()


async def test_ac2_a_start_error_reaches_the_caller() -> None:
    flow = _workflow("Failing")
    register_work_classes({flow: "interactive"})
    failing = Recorder(failure=RuntimeError("temporal is down"))
    configure_temporal_client(cast(Client, failing))
    try:
        with pytest.raises(RuntimeError, match="temporal is down"):
            await dispatch(
                flow,
                "x",
                id="wf-6",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
    finally:
        configure_temporal_client(None)


async def test_ac2_dispatch_logs_the_workflow_and_its_class(
    client: Recorder, capsys: pytest.CaptureFixture[str]
) -> None:
    flow = _workflow("Logged")
    register_work_classes({flow: "background"})
    await dispatch(
        flow,
        "client-content-must-not-be-logged",
        id="wf-7",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
    )
    captured = capsys.readouterr()
    lines = [
        cast("dict[str, object]", json.loads(line))
        for line in (captured.out + captured.err).splitlines()
        if line.strip().startswith("{")
    ]
    [line] = [entry for entry in lines if entry.get("event") == "dispatch.started"]
    assert line["workflow"] == "Logged"
    assert line["work_class"] == "background"
    assert "client-content-must-not-be-logged" not in json.dumps(line)


# --- contract revision 1 -------------------------------------------------------------------------


def test_ac1_the_classes_live_in_a_leaf_module_that_dispatch_re_exports() -> None:
    from abacus.kernel import work_class as leaf

    assert leaf.WORK_CLASSES == WORK_CLASSES == CLASSES
    assert get_args(leaf.WorkClass) == CLASSES


@pytest.mark.parametrize("work_class", CLASSES)
def test_ac1_a_class_queue_maps_back_to_its_class(work_class: WorkClass) -> None:
    assert work_class_of_queue(queue_for(work_class)) == work_class


@pytest.mark.parametrize("queue", ["abacus", "", "abacus-urgent", "other-interactive"])
def test_ac16_the_legacy_queue_and_any_other_queue_have_no_class(queue: str) -> None:
    assert work_class_of_queue(queue) is None


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("abacus.modules.connections.retrievals", "interactive"),
        ("abacus.modules.agents.screenings", "time_sensitive"),
    ],
)
def test_ac4_importing_a_starter_module_alone_registers_its_workflow(
    module: str, expected: str
) -> None:
    """In a clean registry: drop every `abacus` module, import only the starter, and ask the
    freshly imported kernel. The process's own modules are put back afterwards."""
    saved = {name: m for name, m in sys.modules.items() if name.split(".")[0] == "abacus"}
    try:
        for name in saved:
            del sys.modules[name]
        starter = importlib.import_module(module)
        fresh = sys.modules["abacus.kernel.dispatch"]
        flow = next(iter(starter.WORKFLOWS))  # the module's first (its namesake) workflow
        assert fresh.work_class_of(flow) == expected
        for other, work_class in starter.WORKFLOWS.items():
            assert fresh.work_class_of(other) == work_class
    finally:
        for name in [n for n in sys.modules if n.split(".")[0] == "abacus"]:
            del sys.modules[name]
        sys.modules.update(saved)
