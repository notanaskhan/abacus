"""A-04-T28 (TASK-3233): the `planning` slice's events, without a database. Loading them through
the services is `tests/integration/test_a04t28_planning_loaded.py`."""

from __future__ import annotations

from collections import Counter

from abacus_tools.synthetic.scenarios.brightwater_hale import planning_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import HANDLERS, expand_slices
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import slice_events


def test_every_event_has_a_handler_and_the_slice_brings_its_needs() -> None:
    events = slice_events(planning_slice.SLICE)
    assert {e.kind for e in events} <= set(HANDLERS)
    assert len({e.label for e in events}) == len(events)
    expanded = expand_slices((planning_slice.SLICE,))
    assert expanded[-1] == planning_slice.SLICE
    assert set(planning_slice.NEEDS) <= set(expanded)


def test_the_day_runs_in_the_designs_order() -> None:
    times = {e.label.split(":", 2)[-1]: e.at for e in slice_events(planning_slice.SLICE)}
    assert times["risks-recorded"].strftime("%H:%M") == "10:15"
    assert times["ic-exceptions"].strftime("%H:%M") == "12:20"
    assert times["risks-routed"].strftime("%H:%M") == "12:31"
    assert times["risks-approved"].strftime("%H:%M") == "16:40"


def test_ra_is_reviewed_at_4_52_after_its_l1_and_v3_is_reassessed_on_oct_6() -> None:
    """AUD-05 d and AUD-07 d (TASK-6407, DEC-2957)."""
    events = {e.label.split(":", 2)[-1]: e for e in slice_events(planning_slice.SLICE)}
    paper, l1, review = (
        events["ra-paper"],
        events["ra-signed:1"],
        events["ra-signed:3"],
    )
    assert paper.at < l1.at < review.at
    assert (review.actor, review.at.strftime("%b %d %H:%M")) == ("HL", "Sep 14 16:52")
    assert l1.actor == "MD"
    assert {e.data["paper"] for e in (l1, review)} == {planning_slice.RA_PAPER}
    raised, decided = events["materiality-reassessed"], events["materiality-no-change"]
    assert raised.at.strftime("%b %d") == decided.at.strftime("%b %d") == "Oct 06"
    assert (raised.actor, decided.actor) == ("HL", "MO")
    assert raised.at < decided.at


def test_aud08_register_is_r1_to_r10_with_r3_proposed_and_r5_rebuttal() -> None:
    risks = planning_slice.RISKS
    assert [r.code for r in risks] == [f"R{n}" for n in range(1, 11)]
    assert {r.code: r.proposal for r in risks if r.proposal} == {
        "R3": "proposed",
        "R5": "rebuttal_proposed",
    }
    assert risks[0].presumption == "management_override"


def test_aud09_has_seven_exceptions_1_sd_3_d_3_for_resolution() -> None:
    severities = Counter(x.severity for x in planning_slice.EXCEPTIONS)
    assert severities == {"significant_deficiency": 1, "deficiency": 3, None: 3}
    assert [x.row for x in planning_slice.EXCEPTIONS] == list(range(2, 9))
    assert all(x.coso is None for x in planning_slice.EXCEPTIONS if x.severity is None)
