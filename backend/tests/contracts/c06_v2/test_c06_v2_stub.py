"""P-10-T09 (TASK-5109; SPEC-647): C6 v2's stub. Every run v2 operation and event type is in the
generated document; the #4118 and #4127 examples validate against the schemas; a human-only route
carries no agent cell."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from abacus.api.export_openapi import document
from abacus.modules.agents.runs_v2_contract import (
    RUN_EVENT_TYPES,
    BlockedOnOut,
    RunCountersOut,
    RunEventOut,
    RunV2Out,
)

ROUTES = {
    ("get", "/v1/agent-runs/{run_id}/events"),
    ("post", "/v1/engagements/{engagement_id}/runs"),
    ("put", "/v1/engagements/{engagement_id}/auto-mode"),
    ("post", "/v1/agent-runs/{run_id}/plan/approve"),
    ("post", "/v1/agent-runs/{run_id}/plan/edit"),
    ("post", "/v1/agent-runs/{run_id}/plan/cancel"),
    ("post", "/v1/agent-runs/{run_id}/questions/{question_id}/answer"),
    ("post", "/v1/agent-runs/{run_id}/questions/{question_id}/skip"),
    ("post", "/v1/agent-runs/{run_id}/messages"),
    ("post", "/v1/agent-runs/{run_id}/steps/{step_id}/retry"),
    ("post", "/v1/agent-runs/{run_id}/stop"),
    ("post", "/v1/agent-runs/{run_id}/sign-off"),
    ("post", "/v1/agent-feedback"),
    ("get", "/v1/agents/capabilities"),
    ("get", "/v1/workbench/sessions/{session_id}"),
    ("post", "/v1/workbench/sessions/{session_id}/messages"),
    ("get", "/v1/workbench/sessions/{session_id}/events"),
    ("get", "/v1/me/agent-events"),
    ("get", "/v1/events"),
    ("post", "/v1/events/{stream_id}/topics"),
    ("get", "/v1/firm/usage"),
    ("get", "/v1/engagements/{engagement_id}/effort"),
}


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_the_generated_document_has_every_operation(method: str, path: str) -> None:
    paths = cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])
    assert "501" in cast(dict[str, object], paths[path][method]["responses"])


def _run(**overrides: object) -> RunV2Out:
    base: dict[str, object] = {
        "id": uuid4(),
        "run_number": 4118,
        "title": "Season Progress Reporter",
        "state": "succeeded",
        "mode": "run",
        "trigger_kind": "manual",
        "initiator_name": "Hannah Leclerc",
        "counters": RunCountersOut(records_read=2625, citations_count=79, agent_ms=161000),
        "version": 1,
        "allowed_actions": ["sign_off"],
    }
    return RunV2Out.model_validate(base | overrides)


def test_run_4118_validates_and_its_records_foot() -> None:
    run = _run()
    assert run.counters.records_read == 224 + 214 + 241 + 1946
    assert RunV2Out.model_validate_json(run.model_dump_json()) == run


def test_run_4127_blocks_on_a_partner_decision() -> None:
    run = _run(
        run_number=4127,
        title="Northwind engagement run",
        state="blocked_on_decision",
        trigger_kind="engagement_plan",
        blocked_on=BlockedOnOut(kind="decision", id=uuid4(), role="engagement_partner"),
        allowed_actions=["stop"],
    )
    assert run.blocked_on is not None
    assert run.blocked_on.role == "engagement_partner"


def test_event_types_are_the_contract_list() -> None:
    assert {"run.state", "step.state", "item.appended", "plan.decided", "locked", "resync"} <= (
        RUN_EVENT_TYPES
    )
    assert len(RUN_EVENT_TYPES) == 15


def test_a_restricted_item_travels_by_reference() -> None:
    event = RunEventOut(
        seq=18343,
        type="item.appended",
        run_id=uuid4(),
        ref_id=uuid4(),
        ref_only=True,
        at=datetime(2026, 9, 14, 14, 24, tzinfo=UTC),
    )
    assert event.item is None
