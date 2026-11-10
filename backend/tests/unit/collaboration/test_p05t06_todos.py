"""P-05-T06 (TASK-6603; SPEC-650 AC-23, AC-29): My to-dos bands, without a database. The HTTP
acceptance suite is P-05-T07's."""

from __future__ import annotations

from datetime import date

from abacus.modules.collaboration.repository import bucket_of
from abacus.modules.collaboration.todos import MAX_CHECKLIST, TODO_ANCHORS, if_match_version

E0 = date(2026, 9, 14)  # Marcus at E0, Mon Sep 14, 2026, 12:40 PM CT


def test_ac29_marcus_bands_foot_one_one_two() -> None:
    dues = [date(2026, 9, 11), E0, date(2026, 9, 16), date(2026, 9, 18)]
    bands = [bucket_of(d, E0) for d in dues]
    assert bands == ["overdue", "today", "this_week", "this_week"]
    assert bands.count("overdue") + bands.count("today") + bands.count("this_week") == 4


def test_ac23_overdue_is_derived_from_the_due_date_alone() -> None:
    assert bucket_of(date(2026, 9, 18), date(2026, 9, 19)) == "overdue"
    assert bucket_of(date(2026, 9, 21), E0) == "later"  # next Monday is not this week
    assert bucket_of(date(2026, 9, 20), E0) == "this_week"  # Sunday closes the week
    assert bucket_of(None, E0) == "no_date"


def test_the_if_match_header_reads_a_version() -> None:
    assert if_match_version("3") == 3
    assert if_match_version('"3"') == 3
    assert if_match_version('W/"4"') == 4


def test_a_to_do_anchor_takes_no_locator_and_the_checklist_holds_eight() -> None:
    assert TODO_ANCHORS.locator_keys == frozenset()
    assert MAX_CHECKLIST == 8
