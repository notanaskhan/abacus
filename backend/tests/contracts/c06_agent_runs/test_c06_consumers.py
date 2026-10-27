"""C6 v1 consumer tests (Q-02-T45; ADR-169 §4; DEC-595, DEC-596) for the two consumers the row
names: G-02 (the audit log links an agent's audited act to its run and checks the run record's
fingerprint) and A-01 (the archive packages each run record and verifies it). Schema and matrix
only: the routes are live, and their behaviour is held by `agent_tests/test_run_records.py` and
the Q-02-T46 independent suite."""

from __future__ import annotations

import json
from typing import cast

from abacus.api.export_openapi import document
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
RUN = "/v1/agent-runs/{run_id}"
LIST = "/v1/engagements/{engagement_id}/agent-runs"
RECORD = "/v1/agent-runs/{run_id}/record"


def _props(model: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[model]["properties"])


def _response(path: str) -> str:
    content = cast(Json, cast(Json, PATHS[path]["get"]["responses"])["200"])["content"]
    schema = cast(Json, cast(Json, cast(Json, content)["application/json"])["schema"])
    ref = schema.get("$ref") or cast(Json, schema.get("items", {})).get("$ref")
    return str(ref).rsplit("/", 1)[-1]


def test_g02_the_run_summary_carries_the_record_fingerprint_and_stage() -> None:
    # G-02 links an audited agent act to its run and shows whether its record is persisted.
    assert _response(RUN) == "RunViewOut"
    summary = _props("AgentRunOut")
    for field in ("id", "state", "state_reason", "outcome", "stage"):
        assert field in summary, field
    assert {"record_sha256", "record_persisted_at"} <= summary.keys()
    stage = cast(list[str], summary["stage"]["enum"])
    assert sorted(stage) == ["live", "shadow"]


def test_g02_the_list_summary_is_the_same_model() -> None:
    assert _response(LIST) == "AgentRunOut"


def test_a01_the_run_record_has_the_fields_an_archive_verifies() -> None:
    # A-01 packages each record and re-computes record_sha256 over its stored fields.
    assert _response(RECORD) == "RunRecordOut"
    record = _props("RunRecordOut")
    for field in (
        "run_id",
        "engagement_id",
        "capability",
        "spec_version",
        "stage",
        "records_read",
        "citations",
        "outcome",
        "record_sha256",
        "persisted_at",
    ):
        assert field in record, field


def test_both_consumers_read_under_agent_run_read_and_the_agent_is_denied() -> None:
    for path in (RUN, LIST, RECORD):
        assert PATHS[path]["get"].get("x-abacus-action", "agent_run.read") == "agent_run.read"
    rule = RULES["agent_run.read"]
    assert rule.decisions.get("agent") in (None, "deny")
