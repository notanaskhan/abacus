"""I-02-T13 (TASK-7913; I-02 §4.4, F3; SPEC-654; DEC-4916, DEC-4917): briefing dispatch and
freshness (red).

Row acceptance: "Two concurrent first opens start one run per engagement, a real-firm tenant
records boundary-unavailable rows with zero model calls, and a gate signed after 9:24 drops its
why line until the rebuild lands."
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from abacus.modules.agents.briefing import dispatch as d

NOW = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def _row(status: str, minutes_ago: int, built_ago: int | None = None) -> SimpleNamespace:
    created = NOW - timedelta(minutes=minutes_ago)
    built = None if built_ago is None else NOW - timedelta(minutes=built_ago)
    return SimpleNamespace(status=status, created_at=created, built_at=built, seq=1)


def test_ac_a_building_row_in_flight_is_left_alone() -> None:
    """Guard: the second of two concurrent opens finds the first's claimed row (under the
    advisory lock) and starts nothing."""
    assert d.due([_row("building", 1)], "interactive", NOW) == "in_flight"
    assert d.due([_row("building", 1)], "force", NOW) == "in_flight"
    assert d.due([_row("building", 30)], "interactive", NOW) == "build"  # stale claim


def test_ac_dispatch_claims_under_a_lock_before_starting() -> None:
    source = inspect.getsource(d.ensure_briefings)
    lock = source.index("_LOCK")
    claim = source.index('"status": "building"')
    start = source.index("start_engagement_run(")
    assert lock < claim < start


def test_ac_first_open_builds_what_is_missing_only() -> None:
    assert d.due([], "interactive", NOW) == "build"
    assert d.due([_row("ready", 60, 60)], "interactive", NOW) == "fresh"
    assert d.due([_row("unavailable", 60, 60)], "interactive", NOW) == "fresh"


def test_ac_background_rebuilds_are_debounced_and_capped() -> None:
    assert d.due([_row("ready", 60, 5)], "background", NOW) == "debounced"
    six = [_row("ready", 300, 200) for _ in range(d.MAX_BACKGROUND)]
    assert d.due(six, "background", NOW) == "limit"
    assert d.due([_row("ready", 60, 20)], "background", NOW) == "build"


def test_ac_unavailable_reasons_are_the_tables_closed_set() -> None:
    assert d.unavailable_reason("consent_7216") == "consent_7216"
    assert d.unavailable_reason("budget_exhausted") == "budget_soft_limit"
    assert d.unavailable_reason("not_synthetic") == "boundary_refused:not_synthetic"
    assert d.unavailable_reason(None) == "boundary_refused:unavailable"
    assert d.unavailable_reason("weird-Thing!") == "boundary_refused:weird_thing_"


def test_ac_a_refused_capability_records_unavailable_with_no_run() -> None:
    """Guard: readiness is read before the claim; not ready records `unavailable` and
    `continue`s before any run starts (zero model calls)."""
    source = inspect.getsource(d.ensure_briefings)
    ready_at = source.index("capability_ready(")
    unavailable_at = source.index('"status": "unavailable"')
    start_at = source.index("start_engagement_run(")
    assert ready_at < unavailable_at < start_at
    branch = source[unavailable_at:start_at]
    assert "continue" in branch


def test_ac_at_most_three_at_once() -> None:
    assert d.MAX_PARALLEL == 3
    assert "room <= 0" in inspect.getsource(d.ensure_briefings)


def test_ac_a_signed_gate_drops_its_why_line() -> None:
    blocks = {
        "summary": {"version": 1, "parts": []},
        "why": [
            {"gate_id": "g-signed", "line": {"version": 1, "parts": [{"kind": "p"}]}},
            {"gate_id": "g-open", "line": {"version": 1, "parts": [{"kind": "p"}]}},
        ],
    }
    lines = d.current_why(blocks, {"g-open"})
    assert set(lines) == {"g-open"}
    assert d.current_why(None, {"g-open"}) == {}


def test_ac_the_snapshot_holds_no_text() -> None:
    assert d._ints({"count": 3, "label": "Ridgeline", "flag": True}) == {"count": 3}  # pyright: ignore[reportPrivateUsage] -- the filter under test
