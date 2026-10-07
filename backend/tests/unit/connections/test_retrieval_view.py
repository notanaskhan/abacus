"""SPEC-003 AC-13: what a retrieval is reported as while it waits for a work slot (TASK-018
interface contract 018b, "API", and contract revision 1).

A run waiting for a slot stays `running` in the database with a `queued_reason`; callers are told
`queued`, and never `running` while it waits. Expectations come from the contract, not the
implementation.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime

import pytest

from abacus.modules.connections.routes import RetrievalOut
from abacus.modules.connections.service import RetrievalView

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def _view(
    status: str, reason: str | None = None, estimate: datetime | None = None
) -> RetrievalView:
    return RetrievalView(
        uuid.uuid4(),
        uuid.uuid4(),
        status,
        "capacity_timeout" if status == "failed" else None,
        None,
        NOW,
        None if status == "running" else NOW,
        reason,
        estimate,
    )


@pytest.mark.parametrize(
    "reason", ["firm_cap", "engagement_cap", "class_capacity", "provider_capacity", "deferred"]
)
def test_ac13_a_running_run_with_a_reason_is_reported_queued(reason: str) -> None:
    assert _view("running", reason, NOW).reported_status == "queued"
    assert _view("running", reason, None).reported_status == "queued"  # no estimate: still queued


def test_ac13_a_running_run_without_a_reason_is_reported_running() -> None:
    assert _view("running").reported_status == "running"


@pytest.mark.parametrize("status", ["succeeded", "failed", "failed_validation"])
def test_ac13_a_run_that_ended_is_reported_as_it_ended(status: str) -> None:
    assert _view(status).reported_status == status


def test_ac13_the_stored_status_is_left_alone_for_the_services_own_checks() -> None:
    assert _view("running", "firm_cap").status == "running"


def test_ac13_the_defaults_mean_not_queued() -> None:
    view = RetrievalView(uuid.uuid4(), uuid.uuid4(), "running", None, None, NOW, None)
    assert (view.queued_reason, view.estimated_start_at) == (None, None)
    assert view.reported_status == "running"


def test_ac13_the_response_carries_queued_and_never_running_for_a_waiting_run() -> None:
    view = _view("running", "class_capacity", NOW)
    body = RetrievalOut.model_validate(
        {**dataclasses.asdict(view), "status": view.reported_status}, from_attributes=False
    ).model_dump(mode="json")
    assert body["status"] == "queued"
    assert body["queued_reason"] == "class_capacity"
    assert body["estimated_start_at"] is not None


def test_ac13_the_response_admits_queued_as_a_status() -> None:
    view = _view("running", "firm_cap")
    RetrievalOut.model_validate(
        {**dataclasses.asdict(view), "status": "queued"}, from_attributes=False
    )
    with pytest.raises(ValueError, match="status"):
        RetrievalOut.model_validate(
            {**dataclasses.asdict(view), "status": "waiting"}, from_attributes=False
        )
