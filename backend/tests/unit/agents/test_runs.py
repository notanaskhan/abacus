"""SPEC-318 (TASK-461): run states, output counts and the canonical trace export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from abacus.modules.agents.models import AgentRun
from abacus.modules.agents.runs import (
    AGENT_LABEL,
    RUNTIME_LABEL,
    RunSummary,
    Trace,
    TraceRow,
    canonical,
    duration_ms,
    output_counts,
    state_of,
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
