"""P-05-T12 (TASK-6706): the `collaboration` slice's events, without a database. The same figures
as fixture mode (`apps/web/src/fixtures/seed/collaboration.ts`): SHL-18a's comment, SHL-17a's
to-do, and Marcus's 4 open to-dos = 1 overdue + 1 today + 2 this week."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from abacus_tools.synthetic.scenarios.brightwater_hale import collaboration_slice as slice_
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import HANDLERS, expand_slices
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events

TS_SEED = (
    Path(__file__).resolve().parents[4] / "apps/web/src/fixtures/seed/collaboration.ts"
).read_text(encoding="utf-8")


def test_every_event_has_a_handler_and_the_slice_brings_its_needs() -> None:
    events = slice_events(slice_.SLICE)
    assert {e.kind for e in events} <= set(HANDLERS)
    assert len({e.label for e in events}) == len(events) == 1 + len(slice_.TODOS)
    expanded = expand_slices((slice_.SLICE,))
    assert expanded[-1] == slice_.SLICE
    assert set(slice_.NEEDS) <= set(expanded)


def test_shl17f_marcus_has_4_open_to_dos_1_plus_1_plus_2() -> None:
    mine = [t for t in slice_.TODOS if t.assignee == "MD"]
    buckets = Counter(slice_.bucket_of(t.due_on, slice_.LIST_AT.date()) for t in mine)
    assert len(mine) == 4
    assert buckets == {"overdue": 1, "today": 1, "this_week": 2}
    assert all(t.at <= slice_.LIST_AT for t in mine)


def test_shl18a_and_shl17a_match_fixture_mode() -> None:
    assert slice_.THREAD_BODY in TS_SEED
    assert slice_.THREAD_AT.strftime("%H:%M") == "12:35"
    for todo in slice_.TODOS:
        assert todo.title in TS_SEED, todo.key
        assert todo.due_on.isoformat() in TS_SEED, todo.key
        for item in todo.checklist:
            assert item in TS_SEED
    row6 = next(t for t in slice_.TODOS if t.key == "row6")
    assert row6.by == "MO" and row6.locator == {"sheet": "Exceptions", "row": 6}
    assert len(row6.checklist) == 4


def test_the_thread_mentions_hannah_on_exceptions_a3() -> None:
    thread = next(e for e in slice_events(slice_.SLICE) if e.kind == "collaboration.thread_seeded")
    assert thread.actor == "MO"
    assert thread.data["locator"] == {"sheet": "Exceptions", "cell": "A3"}
    assert thread.data["mention"] == ["HL"]
