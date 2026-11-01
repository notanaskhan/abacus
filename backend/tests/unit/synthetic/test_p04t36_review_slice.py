"""P-04-T36 (TASK-2923; DEC-1969): the `review` slice's events, without a database. The loaded
scenario (sign-offs, notes, cards, issues, checkpoints through the services) is the integration
pass's and P-04-T37's golden suite's."""

from __future__ import annotations

from collections import Counter

from abacus_tools.synthetic.scenarios.brightwater_hale import review_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    HANDLERS,
    expand_slices,
    replay_order,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events


def test_every_event_has_a_handler_and_the_slice_brings_its_needs() -> None:
    events = slice_events(review_slice.SLICE)
    assert {e.kind for e in events} <= set(HANDLERS)
    assert all(e.slice == review_slice.SLICE for e in events)
    assert len({e.label for e in events}) == len(events)
    expanded = expand_slices((review_slice.SLICE,))
    assert expanded[-1] == review_slice.SLICE
    assert set(review_slice.NEEDS) <= set(expanded)


def test_ridgeline_has_txp10s_eleven_open_issues_5_waiting_and_6_review_points() -> None:
    assert len(review_slice.ISSUES) == 11
    assert Counter(i.kind for i in review_slice.ISSUES) == {
        "waiting_on_client": 5,
        "review_point": 6,
    }
    titles = {i.title for i in review_slice.ISSUES}
    assert "Tax-exempt interest 6,200 omitted from the capital rollforward" in titles
    assert "§743(b) placeholder 28,595 pending the §754 decision" in titles
    assert review_slice.ISSUE_BLOCKS == ("final_approval",)


def test_northwind_materiality_is_proposed_then_decided_by_margaret_then_reassessed() -> None:
    events = replay_order(tuple(slice_events(review_slice.SLICE)))
    kinds = [e.kind for e in events if e.client == review_slice.NORTHWIND]
    assert kinds.index("ledger.northwind_tb_recorded") < kinds.index(
        "assurance.northwind_tb_adopted"
    )
    assert kinds.index("assurance.northwind_tb_adopted") < kinds.index(
        "assurance.materiality_proposed"
    )
    decided = [e for e in events if e.kind == "review.materiality_decided"]
    assert [(e.actor, e.data["option_key"]) for e in decided] == [
        ("MO", "rate_1_5"),
        ("MO", "no_change"),
    ]
    assert all(e.data["rationale"] for e in decided)


def test_the_tb_l1_precedes_the_two_notes_assigned_to_the_preparer() -> None:
    events = replay_order(tuple(slice_events(review_slice.SLICE)))
    signed = next(e for e in events if e.kind == "review.northwind_tb_signed")
    notes = [e for e in events if e.kind == "review.northwind_note_raised"]
    assert (signed.actor, signed.data["level"]) == ("MD", 1)
    assert [(n.actor, n.data["cell"]) for n in notes] == [("HL", "RA!C14"), ("MO", "RA!C22")]
    assert all(n.at > signed.at for n in notes)
