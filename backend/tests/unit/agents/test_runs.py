"""SPEC-318 (TASK-461): run states, output counts and the canonical trace export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from abacus.modules.agents.models import AgentRun
from abacus.modules.agents.repository import RunWriteRow
from abacus.modules.agents.runs import (
    AGENT_LABEL,
    RUNTIME_LABEL,
    RunItem,
    RunSummary,
    Trace,
    TraceRow,
    canonical,
    duration_ms,
    output_counts,
    page_items,
    run_record_sha256,
    state_of,
    written_counts,
)

T0 = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _run(status: str, queued_reason: str | None = None) -> AgentRun:
    return cast(AgentRun, SimpleNamespace(status=status, queued_reason=queued_reason))


@pytest.mark.parametrize(
    ("status", "queued", "state"),
    [
        ("running", None, "running"),
        ("running", "concurrency", "queued"),
        ("completed", None, "succeeded"),
        ("escalated", None, "needs_input"),
        ("failed", None, "failed"),
    ],
)
def test_ac2_run_states_map_to_the_status_words(
    status: str, queued: str | None, state: str
) -> None:
    assert state_of(_run(status, queued)) == state


def test_ac2_duration_is_computed_and_open_runs_have_none() -> None:
    assert duration_ms(T0, T0 + timedelta(seconds=2, milliseconds=5)) == 2005
    assert duration_ms(T0, None) is None


def test_ac4_output_counts_count_list_keys_only() -> None:
    assert output_counts({"assertions": [1, 2], "summary": "x", "flags": []}) == [
        ("assertions", 2),
        ("flags", 0),
    ]
    assert output_counts(None) == []


def test_ac1_every_agent_has_a_label_and_the_model_id_is_never_the_runtime() -> None:
    assert "Engagement agent" in AGENT_LABEL.values()
    assert "claude" not in RUNTIME_LABEL.lower()


def _trace() -> Trace:
    rid = UUID("00000000-0000-4000-8000-000000000461")
    run = RunSummary(
        rid, "evidence.screener", "Evidence screener", "succeeded", T0, T0, 0, "Dana", None
    )
    row = TraceRow(1, T0, "start", "Run started", "done", "requested", "Dana")
    return Trace(
        run, RUNTIME_LABEL, "US", "never", 1, 10, 5, [row], [], [("citations", 2)], "text"
    )


def test_ac6_the_export_is_canonical_and_deterministic() -> None:
    body = canonical(_trace())
    assert body == canonical(_trace())
    assert b'"started_at":"2026-10-22T12:00:00+00:00"' in body
    assert body.index(b'"agent"') < body.index(b'"agent_label"')  # sorted keys


def _write(kind: str) -> RunWriteRow:
    return RunWriteRow(kind, UUID(int=1), None, None, "k", "pending", T0, None, None, None)


def test_c6_v1_counts_the_runs_suggestions_and_proposals() -> None:
    assert written_counts([_write("suggestion"), _write("proposal"), _write("suggestion")]) == [
        ("proposals", 1),
        ("suggestions", 2),
    ]
    assert written_counts([]) == []


def test_c6_v1_the_run_record_fingerprint_is_stable_and_follows_the_record() -> None:
    fields = {
        "id": UUID(int=7),
        "agent_id": "evidence.screener",
        "spec_version": 3,
        "engagement_id": UUID(int=8),
        "evidence_version_id": None,
        "inbox_file_id": None,
        "methodology_version_id": None,
        "status": "completed",
        "context_hash": "a" * 64,
        "failure_code": None,
        "started_at": T0,
        "finished_at": T0,
        "output": {"citations": [1]},
    }
    run = cast(AgentRun, SimpleNamespace(**fields))
    same = cast(AgentRun, SimpleNamespace(**fields))
    failed = cast(AgentRun, SimpleNamespace(**{**fields, "status": "failed"}))
    assert run_record_sha256(run) == run_record_sha256(same)
    assert run_record_sha256(run) != run_record_sha256(failed)
    assert len(run_record_sha256(run)) == 64


def test_dec87_the_runtime_is_named_never_the_model() -> None:
    assert RUNTIME_LABEL == "Accrued Agent runtime"


def _item(kind: str, seconds: int, code: str = "c") -> RunItem:
    return RunItem(0, kind, T0 + timedelta(seconds=seconds), code, None, None, None, None, None)  # type: ignore[arg-type]  # kind is one of the four


def test_p09_story_1_3_items_are_numbered_by_time_and_paged_after_seq() -> None:
    raw = [_item("decision", 5), _item("narration", 1), _item("tool_card", 0), _item("failure", 9)]
    items, last, resync = page_items(raw, 0)
    assert [(i.seq, i.kind) for i in items] == [
        (1, "tool_card"),
        (2, "narration"),
        (3, "decision"),
        (4, "failure"),
    ]
    assert (last, resync) == (4, False)
    later, _, _ = page_items(raw, 2)
    assert [i.seq for i in later] == [3, 4]
    assert page_items(raw, 4)[0] == []


def test_p09_story_1_3_a_client_ahead_of_the_server_resyncs() -> None:
    items, last, resync = page_items([_item("tool_card", 0)], 7)
    assert resync and last == 1 and [i.seq for i in items] == [1]


def test_p09_the_tool_card_comes_first_at_the_same_instant() -> None:
    items, _, _ = page_items([_item("narration", 0), _item("tool_card", 0)], 0)
    assert items[0].kind == "tool_card"
