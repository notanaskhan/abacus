"""AC-2, AC-4: agent specs carry a work class, and screening starts through `dispatch`
(TASK-018 interface contract, "Agent specs" and "Registrations"; SPEC-003 Q1, Q2; ADR-071, ADR-105).

A spec without `work_class`, `essential` or `cheaper_tiers`, or with an unknown class, fails
validation, so `AGENTS` does not load. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.dispatch import work_class_of
from abacus.kernel.temporal import configure_temporal_client
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents import spec as spec_module
from abacus.modules.agents.api import (
    SCREENER,
    AgentSpec,
    ScreeningInput,
    ScreeningWorkflow,
    start_screening,
    workflow_id,
)
from abacus.modules.agents.spec import AGENTS
from abacus.modules.agents.specs import _specs

SCREENER_YAML = Path(_specs.__file__).parent / "evidence.screener.yaml"
load_specs = cast(Callable[[], dict[str, AgentSpec]], vars(spec_module)["_load"])
TENANT = uuid.uuid4()
EVENT = uuid.uuid4()
VERSION = uuid.uuid4()
PERSON = uuid.uuid4()


def _raw() -> dict[str, object]:
    return copy.deepcopy(_specs.SPECS[SCREENER])


# --- the spec fields (AC-4; ADR-105) -------------------------------------------------------------


def test_ac4_the_screener_is_time_sensitive_essential_and_has_no_cheaper_tier() -> None:
    found = AGENTS[SCREENER]
    assert found.work_class == "time_sensitive"
    assert found.essential is True
    assert found.cheaper_tiers == ()


def test_ac4_the_screeners_yaml_declares_the_three_fields() -> None:
    loaded = yaml.safe_load(SCREENER_YAML.read_text())
    assert loaded["work_class"] == "time_sensitive"
    assert loaded["essential"] is True
    assert loaded["cheaper_tiers"] == []


@pytest.mark.parametrize("missing", ["work_class", "essential", "cheaper_tiers"])
def test_ac4_a_spec_without_the_field_is_refused(missing: str) -> None:
    raw = _raw()
    del raw[missing]
    with pytest.raises(ValidationError):
        AgentSpec.model_validate(raw)


@pytest.mark.parametrize("missing", ["work_class", "essential", "cheaper_tiers"])
def test_ac4_the_loader_raises_for_a_spec_without_the_field(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    raw = _raw()
    del raw[missing]
    monkeypatch.setattr(spec_module, "SPECS", {SCREENER: raw})
    with pytest.raises(ValidationError):
        load_specs()


@pytest.mark.parametrize("unknown", ["", "urgent", "time-sensitive", "INTERACTIVE", "legacy", 3])
def test_ac4_an_unknown_work_class_is_refused(unknown: object) -> None:
    with pytest.raises(ValidationError):
        AgentSpec.model_validate({**_raw(), "work_class": unknown})


def test_ac4_the_loader_raises_for_an_unknown_work_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spec_module, "SPECS", {SCREENER: {**_raw(), "work_class": "urgent"}})
    with pytest.raises(ValidationError):
        load_specs()


@pytest.mark.parametrize("work_class", ["interactive", "time_sensitive", "background", "batch"])
def test_ac4_each_of_the_four_classes_is_accepted(work_class: str) -> None:
    assert AgentSpec.model_validate({**_raw(), "work_class": work_class}).work_class == work_class


@pytest.mark.parametrize("essential", [True, False])
def test_ac4_essential_is_a_boolean(essential: bool) -> None:
    assert AgentSpec.model_validate({**_raw(), "essential": essential}).essential is essential


def test_ac4_cheaper_tiers_may_list_known_tiers() -> None:
    found = AgentSpec.model_validate({**_raw(), "cheaper_tiers": ["small"]})
    assert found.cheaper_tiers == ("small",)


@pytest.mark.parametrize("tiers", [["huge"], [""], ["small", "huge"]])
def test_ac4_cheaper_tiers_must_be_known_tiers(tiers: list[str]) -> None:
    with pytest.raises(ValidationError):
        AgentSpec.model_validate({**_raw(), "cheaper_tiers": tiers})


def test_ac4_a_spec_is_still_immutable_with_its_class() -> None:
    with pytest.raises(ValidationError):
        AGENTS[SCREENER].work_class = "batch"


def test_ac2_the_screening_workflow_runs_in_the_screeners_class() -> None:
    assert work_class_of(ScreeningWorkflow) == AGENTS[SCREENER].work_class


# --- start_screening goes through dispatch (AC-2) ------------------------------------------------


class Recorder:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def start_workflow(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))
        if self.failure is not None:
            raise self.failure


@pytest.fixture
def recorder() -> Iterator[Recorder]:
    found = Recorder()
    configure_temporal_client(cast(Client, found))
    yield found
    configure_temporal_client(None)


def _event() -> OutboxEvent:
    return OutboxEvent(
        EVENT,
        TENANT,
        "evidence_version.created",
        {"evidence_version_id": str(VERSION), "requested_by": str(PERSON)},
    )


async def test_ac2_start_screening_starts_the_workflow_on_the_time_sensitive_queue(
    recorder: Recorder,
) -> None:
    await start_screening(_event())
    [(args, kwargs)] = recorder.calls
    assert args == (
        ScreeningWorkflow.run,
        ScreeningInput(str(TENANT), str(VERSION), str(EVENT), str(PERSON)),
    )
    assert kwargs["id"] == workflow_id(TENANT, VERSION)
    assert kwargs["task_queue"] == "abacus-time-sensitive"


async def test_ac2_start_screening_keeps_its_id_policies(recorder: Recorder) -> None:
    await start_screening(_event())
    [(_, kwargs)] = recorder.calls
    # A failed workflow may be started again by a redelivery; a finished one may not.
    assert kwargs["id_reuse_policy"] == WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
    assert kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.USE_EXISTING


async def test_ac2_an_already_started_screening_counts_as_delivered() -> None:
    failing = Recorder(
        failure=WorkflowAlreadyStartedError("screening", "ScreeningWorkflow", run_id="r")
    )
    configure_temporal_client(cast(Client, failing))
    try:
        await start_screening(_event())  # no error
    finally:
        configure_temporal_client(None)
    assert len(failing.calls) == 1


async def test_ac2_any_other_start_error_reaches_the_relay() -> None:
    failing = Recorder(failure=RuntimeError("temporal is down"))
    configure_temporal_client(cast(Client, failing))
    try:
        with pytest.raises(RuntimeError, match="temporal is down"):
            await start_screening(_event())
    finally:
        configure_temporal_client(None)
