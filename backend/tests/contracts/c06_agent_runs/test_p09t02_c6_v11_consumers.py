"""C6 v1.1 consumer contract tests (P-09-T02; TASK-6220; SPEC-648; docs/contracts/agent-runs.md
§10) for SHL-13's dock and WB-09's run-trace drawer.

Row acceptance: "The tests run green in the provider's CI job and fail when any field the dock or
drawer reads is removed from the stub." Every field listed here is one the SHL-13 dock
(`domain/agents/AgentDock.tsx`, `runFeed.ts`, `narrate.ts`) or the WB-09 drawer
(`TraceDrawer.tsx`) reads, or one C6 v1.1 adds for them; removing any from the OpenAPI document
fails the test that names it. The step-detail route exists and authorises before its flag.
"""

from __future__ import annotations

import inspect
import json
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.modules.agents import runs_routes

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])

# The dock (SHL-13): the run list, a run's feed and its tool cards.
DOCK: dict[str, tuple[str, ...]] = {
    "AgentRunOut": (
        "id", "agent", "agent_label", "state", "started_at", "duration_ms", "initiator_name",
        "subject",
    ),
    "RunItemsOut": ("run", "items", "last_seq", "resync", "next_seq"),
    "RunItemOut": ("seq", "kind", "at", "code", "outcome", "detail", "actor", "session_kind"),
    "RunViewOut": ("run", "header", "levels", "access"),
    "RunHeaderOut": ("run_number", "runs_as_name", "trigger_kind", "blocked_on", "counters"),
    "RunProjectionLevelOut": ("level", "total", "done", "running", "queued", "waiting", "blocked"),
}  # fmt: skip

# The drawer (WB-09): the trace, its rows, records read, writes, the summary and a step.
DRAWER: dict[str, tuple[str, ...]] = {
    "RunTraceOut": (
        "run", "rows", "records_read", "summary", "access", "region", "runtime", "training",
    ),
    "TraceRowOut": (
        "seq", "at", "title", "state", "actor", "detail", "phase", "mark", "duration_ms",
    ),
    "RecordsReadOut": ("source", "count", "connection_id", "through"),
    "RunWriteOut": (
        "id", "key", "kind", "at", "decision", "decided_by_name", "state", "approver_name",
        "proposal_id",
    ),
    "TraceSummaryOut": (
        "agent_label", "run_number", "runs_as_name", "trigger_kind", "started_at", "duration_ms",
        "records_read", "citations", "writes_done", "writes_waiting",
    ),
    "TraceStepOut": ("step_id", "title", "args_summary", "records_read", "samples"),
    "TraceSampleOut": ("id", "label", "record_type", "open_route"),
}  # fmt: skip

CASES = [(m, f) for table in (DOCK, DRAWER) for m, fields in table.items() for f in fields]


@pytest.mark.parametrize(("model", "field"), CASES, ids=[f"{m}.{f}" for m, f in CASES])
def test_every_field_the_dock_and_drawer_read_is_on_the_stub(model: str, field: str) -> None:
    assert model in SCHEMAS, model
    properties = cast(dict[str, Json], SCHEMAS[model]["properties"])
    assert field in properties, f"{model}.{field} is read by SHL-13 or WB-09"


@pytest.mark.parametrize(
    "path",
    [
        "/v1/engagements/{engagement_id}/agent-runs",
        "/v1/agent-runs/{run_id}",
        "/v1/agent-runs/{run_id}/items",
        "/v1/agent-runs/{run_id}/trace",
        "/v1/agent-runs/{run_id}/trace/records-read",
        "/v1/agent-runs/{run_id}/trace/writes",
        "/v1/agent-runs/{run_id}/trace/steps/{step_id}",
    ],
)
def test_every_route_the_dock_and_drawer_call_exists(path: str) -> None:
    assert "get" in PATHS[path], path


def test_the_feed_takes_the_after_seq_cursor() -> None:
    parameters = cast(list[Json], PATHS["/v1/agent-runs/{run_id}/items"]["get"]["parameters"])
    assert "after_seq" in {p["name"] for p in parameters}


def test_the_items_response_is_the_feed_model() -> None:
    response = cast(
        Json, cast(Json, PATHS["/v1/agent-runs/{run_id}/items"]["get"]["responses"])["200"]
    )
    schema = cast(Json, cast(Json, cast(Json, response["content"])["application/json"])["schema"])
    assert str(schema["$ref"]).endswith("/RunItemsOut")


def test_the_step_route_authorises_before_its_flag() -> None:
    source = inspect.getsource(runs_routes)
    start = source.index("/trace/steps/{step_id}")
    body = source[start : start + 1500]
    assert body.index("run_view") < body.index("RUN_TRACE_ENABLED")
