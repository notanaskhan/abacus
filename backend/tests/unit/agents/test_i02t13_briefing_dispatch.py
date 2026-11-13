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

import pytest

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
    blocks: dict[str, object] = {
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


# --- I-02-T13 rest (TASK-7930): staleness asks for a background rebuild -----------------------


def test_rest_a_brief_is_stale_when_a_why_gate_closed_since() -> None:
    from abacus.modules.agents.briefing.dispatch import why_gone

    blocks: dict[str, object] = {
        "why": [{"gate_id": "g1", "line": {}}, {"gate_id": "g2", "line": {}}]
    }
    assert not why_gone(blocks, {"g1", "g2", "g3"})
    assert why_gone(blocks, {"g1"})
    assert not why_gone(None, set())
    assert not why_gone({"why": "nope"}, set())


def test_rest_background_builds_only_the_stale_engagements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import uuid
    from datetime import date
    from types import SimpleNamespace
    from typing import Any

    from abacus.modules.agents import api as agents_api
    from abacus.modules.practice.today import assembly, routes
    from abacus.modules.practice.today.contract import TodayBuildIn

    stale, fresh = uuid.uuid4(), uuid.uuid4()
    vm = SimpleNamespace(
        cards=[SimpleNamespace(engagement_id=stale, label="A"),
               SimpleNamespace(engagement_id=fresh, label="B")],
        stale_engagements=[stale],
    )  # fmt: skip
    seen: list[Any] = []  # Any: the dispatch's recorded call

    async def gate(*_a: object) -> None:
        return None

    async def assemble(*_a: object) -> object:
        return vm

    async def snapshot(*_a: object) -> None:
        return None

    async def ensure(_ctx: object, cards: object, mode: str, _on: object) -> object:
        seen.append((cards, mode))
        return SimpleNamespace(started=[1])

    monkeypatch.setattr(routes, "today_gate", gate)
    monkeypatch.setattr(assembly, "assemble", assemble)
    monkeypatch.setattr(agents_api, "write_briefing_snapshot", snapshot)
    monkeypatch.setattr(agents_api, "ensure_briefings", ensure)
    body = TodayBuildIn(brief_date=date(2026, 9, 14), mode="background")
    asyncio.run(routes.today_builds_route(body, object(), "k"))  # type: ignore[arg-type] -- test doubles
    assert seen == [([(stale, "A")], "background")]
