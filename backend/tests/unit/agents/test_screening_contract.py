"""AC-14, AC-17, AC-20: the screening subscription, workflow types, routing publisher and spec
changes that need no services (TASK-011b interface contract: "Subscription", "Relay (kernel)",
"Gateway and spec changes"). Expectations come from the contract, not the implementation."""

from __future__ import annotations

import copy
import dataclasses
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import yaml
from pydantic import ValidationError

from abacus.kernel.uow.relay import Handler, OutboxEvent, RoutingPublisher
from abacus.modules.agents import spec as spec_module
from abacus.modules.agents.activities import INITIATOR_INACTIVE
from abacus.modules.agents.api import (
    ACTIVITIES,
    SCREENER,
    SUBSCRIPTIONS,
    WORKFLOWS,
    AgentSpec,
    ScreeningInput,
    ScreeningWorkflow,
    start_screening,
    workflow_id,
)
from abacus.modules.agents.handoff import ScreeningOutput
from abacus.modules.agents.screenings import EVIDENCE_VERSION_CREATED, screening_input
from abacus.modules.agents.spec import AGENTS, OUTPUT_SCHEMAS
from abacus.modules.agents.specs import _specs
from abacus.modules.agents.workflow_types import (
    CANCELLED,
    FAIL_CODES,
    INTERNAL_ERROR,
    PROVIDER_UNAVAILABLE,
    FailInput,
    RunInput,
    ScreeningOutcome,
)

TENANT = uuid.uuid4()
EVENT = uuid.uuid4()
VERSION = uuid.uuid4()
PERSON = uuid.uuid4()
SCREENER_YAML = Path(_specs.__file__).parent / "evidence.screener.yaml"


def _event(payload: dict[str, object], event_type: str = EVIDENCE_VERSION_CREATED) -> OutboxEvent:
    return OutboxEvent(EVENT, TENANT, event_type, payload)


# --- the subscription ----------------------------------------------------------------------------


def test_ac14_screening_starts_from_evidence_version_created() -> None:
    assert EVIDENCE_VERSION_CREATED == "evidence_version.created"
    assert {"evidence_version.created": start_screening} == SUBSCRIPTIONS
    assert (ScreeningWorkflow,) == WORKFLOWS
    assert len(ACTIVITIES) == 3


def test_ac14_the_workflow_id_is_the_evidence_version() -> None:
    assert workflow_id(VERSION) == f"screening:{VERSION}"


def test_ac14_the_input_is_built_from_the_event_identifiers() -> None:
    built = screening_input(
        _event({"evidence_version_id": str(VERSION), "requested_by": str(PERSON)})
    )
    assert built == ScreeningInput(str(TENANT), str(VERSION), str(EVENT), str(PERSON))


SPELLINGS: dict[str, Callable[[uuid.UUID], str]] = {
    "upper": lambda u: str(u).upper(),
    "hex": lambda u: u.hex,
    "braces": lambda u: "{" + str(u) + "}",
    "urn": lambda u: u.urn,
}


@pytest.mark.parametrize("name", sorted(SPELLINGS))
def test_ac14_uuids_in_the_payload_are_normalised(name: str) -> None:
    spelling = SPELLINGS[name]
    built = screening_input(
        _event(
            {
                "evidence_version_id": spelling(VERSION),
                "requested_by": spelling(PERSON),
            }
        )
    )
    assert built.evidence_version_id == str(VERSION)
    assert built.requested_by == str(PERSON)
    assert built.tenant_id == str(TENANT)
    assert built.event_id == str(EVENT)


def test_ac14_requested_by_absent_or_null_is_none() -> None:
    assert screening_input(_event({"evidence_version_id": str(VERSION)})).requested_by is None
    nulled = screening_input(_event({"evidence_version_id": str(VERSION), "requested_by": None}))
    assert nulled.requested_by is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"requested_by": str(PERSON)},
        {"evidence_version_id": None},
        {"evidence_version_id": "not-a-uuid"},
        {"evidence_version_id": ""},
        {"evidence_version_id": 7},
        {"evidence_version_id": str(VERSION), "requested_by": "not-a-uuid"},
    ],
    ids=lambda p: "-".join(f"{k}={v}" for k, v in p.items()) or "empty",
)
def test_ac14_a_missing_or_malformed_identifier_raises(payload: dict[str, object]) -> None:
    with pytest.raises((KeyError, ValueError, TypeError, AttributeError)):
        screening_input(_event(payload))


# --- workflow payload types ----------------------------------------------------------------------


def test_ac14_the_failure_codes_a_workflow_may_record() -> None:
    assert PROVIDER_UNAVAILABLE == "provider_unavailable"
    assert INTERNAL_ERROR == "internal_error"
    assert CANCELLED == "cancelled"
    assert frozenset({"provider_unavailable", "internal_error", "cancelled"}) == FAIL_CODES
    assert INITIATOR_INACTIVE == "initiator_inactive"


def test_ac14_the_outcome_defaults_to_only_a_status() -> None:
    skipped = ScreeningOutcome("skipped")
    assert (skipped.status, skipped.run_id, skipped.code, skipped.screening_result_id) == (
        "skipped",
        None,
        None,
        None,
    )
    full = ScreeningOutcome("completed", "run", "code", "result")
    assert [full.status, full.run_id, full.code, full.screening_result_id] == [
        "completed",
        "run",
        "code",
        "result",
    ]


def test_ac14_workflow_payloads_hold_identifiers_and_codes_only() -> None:
    # No field can carry a name, an amount or a message: every field is a string (or none).
    for kind in (ScreeningInput, RunInput, FailInput, ScreeningOutcome):
        for field in dataclasses.fields(kind):
            assert str(field.type) in ("str", "str | None"), (kind.__name__, field.name)
    assert [f.name for f in dataclasses.fields(ScreeningInput)] == [
        "tenant_id",
        "evidence_version_id",
        "event_id",
        "requested_by",
    ]
    assert [f.name for f in dataclasses.fields(RunInput)] == ["tenant_id", "run_id"]
    assert [f.name for f in dataclasses.fields(FailInput)] == ["tenant_id", "run_id", "code"]
    assert [f.name for f in dataclasses.fields(ScreeningOutcome)] == [
        "status",
        "run_id",
        "code",
        "screening_result_id",
    ]


# --- RoutingPublisher ----------------------------------------------------------------------------


class Calls:
    def __init__(self) -> None:
        self.log: list[tuple[str, uuid.UUID]] = []

    def handler(self, name: str, *, fail: Exception | None = None) -> Handler:
        async def handle(event: OutboxEvent) -> None:
            self.log.append((name, event.event_id))
            if fail is not None:
                raise fail

        return handle


async def test_ac20_every_handler_for_the_event_type_runs_in_order() -> None:
    calls = Calls()
    publisher = RoutingPublisher(
        {
            "a.happened": [
                calls.handler("first"),
                calls.handler("second"),
                calls.handler("third"),
            ],
            "b.happened": [calls.handler("other")],
        }
    )
    await publisher.publish(_event({}, "a.happened"))
    assert calls.log == [("first", EVENT), ("second", EVENT), ("third", EVENT)]


async def test_ac20_an_event_with_no_handlers_is_published_without_error() -> None:
    calls = Calls()
    publisher = RoutingPublisher({"a.happened": [calls.handler("first")]})
    await publisher.publish(_event({}, "unknown.type"))
    await RoutingPublisher({}).publish(_event({}))
    assert calls.log == []


async def test_ac20_a_handler_error_propagates_so_the_relay_retries() -> None:
    calls = Calls()
    publisher = RoutingPublisher(
        {
            "a.happened": [
                calls.handler("first"),
                calls.handler("broken", fail=ValueError("handler failed")),
                calls.handler("never"),
            ]
        }
    )
    with pytest.raises(ValueError, match="handler failed"):
        await publisher.publish(_event({}, "a.happened"))
    assert [name for name, _ in calls.log] == ["first", "broken"]


# --- spec changes --------------------------------------------------------------------------------


def _raw() -> dict[str, object]:
    return copy.deepcopy(_specs.SPECS[SCREENER])


def test_ac14_the_spec_has_no_escalation_tier_or_input_schema() -> None:
    assert "escalation_tier" not in AgentSpec.model_fields
    assert "input_schema" not in AgentSpec.model_fields
    assert "escalation_tier" not in _raw()
    assert "input_schema" not in _raw()
    text = SCREENER_YAML.read_text()
    assert "escalation_tier" not in text
    assert "input_schema" not in text
    loaded = yaml.safe_load(text)
    assert "escalation_tier" not in loaded
    assert "input_schema" not in loaded


@pytest.mark.parametrize("key", ["escalation_tier", "input_schema"])
def test_ac14_a_spec_still_naming_a_dropped_field_is_refused(key: str) -> None:
    with pytest.raises(ValidationError):
        AgentSpec.model_validate({**_raw(), key: "small"})


def test_ac14_the_output_schema_is_the_screening_output_literal() -> None:
    assert AGENTS[SCREENER].output_schema == "ScreeningOutput"
    assert OUTPUT_SCHEMAS["ScreeningOutput"] is ScreeningOutput
    for other in ("ScreeningResult", "Handoff", "", "screeningoutput"):
        with pytest.raises(ValidationError):
            AgentSpec.model_validate({**_raw(), "output_schema": other})


@pytest.mark.parametrize("steps", [2, 3, 10])
def test_ac14_a_single_call_spec_with_more_than_one_step_fails_at_import(
    monkeypatch: pytest.MonkeyPatch, steps: int
) -> None:
    raw = _raw()
    limits = dict(cast(dict[str, object], raw["limits"]))
    limits["max_steps"] = steps
    monkeypatch.setattr(spec_module, "SPECS", {SCREENER: {**raw, "limits": limits}})
    load = vars(spec_module)["_load"]
    with pytest.raises(ValueError):
        load()
