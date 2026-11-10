"""A-07-T36 (TASK-6609; SPEC-644 AC-36; AU-C 230, AU-C 265): the post-release clocks.

Row acceptance: "Golden clocks hold: an Oct 9 release gives Dec 8 for both clocks, Archive in 5
days on Dec 3, and Overdue on Dec 9."
"""

from __future__ import annotations

from datetime import date

from abacus.modules.assurance import clocks
from abacus.modules.assurance.post_release import due_label, wake_at, workflow_id

RELEASE = date(2026, 10, 9)


def test_ac36_an_oct_9_release_gives_dec_8_for_both_clocks() -> None:
    assert clocks.deadline("archive", RELEASE) == date(2026, 12, 8)
    assert clocks.deadline("au_c_265", RELEASE) == date(2026, 12, 8)


def test_ac36_dec_3_reads_archive_in_5_days_at_risk() -> None:
    found = clocks.read("archive", RELEASE, date(2026, 12, 3))
    assert (found.days_left, found.state) == (5, "at_risk")


def test_ac36_dec_9_is_overdue_and_dec_8_due_today() -> None:
    assert clocks.read("archive", RELEASE, date(2026, 12, 9)).state == "overdue"
    assert clocks.read("au_c_265", RELEASE, date(2026, 12, 9)).state == "overdue"
    assert clocks.read("archive", RELEASE, date(2026, 12, 8)).state == "due_today"


def test_the_oct_22_clock_runs_with_47_days_left_and_red_only_at_7() -> None:
    found = clocks.read("archive", RELEASE, date(2026, 10, 22))
    assert (found.days_left, found.state) == (47, "running")
    assert clocks.read("archive", RELEASE, date(2026, 12, 1)).state == "at_risk"
    assert clocks.read("archive", RELEASE, date(2026, 11, 30)).state == "running"


def test_a_locked_archive_or_a_sent_letter_stops_its_clock() -> None:
    assert clocks.read("archive", RELEASE, date(2026, 12, 9), stopped=True).state == "stopped"


def test_the_release_starts_five_timers_in_order() -> None:
    assert [due_label(t) for t in clocks.timers(RELEASE)] == [
        "archive:deadline_risk@2026-12-01",
        "archive:deadline@2026-12-08",
        "au_c_265:deadline@2026-12-08",
        "archive:overdue@2026-12-09",
        "au_c_265:overdue@2026-12-09",
    ]
    assert wake_at(date(2026, 12, 1)).hour == 9


def test_form_5500_is_due_jul_31_and_oct_15_extended_for_a_calendar_plan_year() -> None:
    assert clocks.form_5500_due(date(2025, 12, 31)) == (date(2026, 7, 31), date(2026, 10, 15))
    assert clocks.form_5500_due(date(2026, 6, 30)) == (date(2027, 1, 31), date(2027, 4, 15))


def test_the_workflow_id_is_one_per_work_item() -> None:
    import uuid

    t, wi = uuid.uuid4(), uuid.uuid4()
    assert workflow_id(t, wi) == f"post_release_clocks:{t}:{wi}"
