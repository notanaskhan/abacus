"""Q-04-T020: every PW1 day has a primary and a named backup, and the rota holds no contacts.
Q-04-T066: the autumn window's every day is covered, and its deadline weeks, and only those, are
on double cover.

Acceptance: a test page reaches N and escalates to AY after 15 minutes (a paging-tool drill,
recorded in the file), and every window day has a named backup (this check, in check-fast).
"""

from __future__ import annotations

import pytest

from abacus_tools import release_windows
from abacus_tools.quality import on_call as oc

HEAD = "---\nupdated: 2027-05-20\n---\n# On-call\n\n"
WINDOWS = (
    "## Windows\n\n| Window | Starts | Ends | Live firms |\n|---|---|---|---|\n"
    "| PW1 | 2027-06-01 | 2027-06-07 | PF-A1 |\n\n"
)
ROTA = (
    "## Rota\n\n| Window | From | To | Primary | Backup | Cover | Notes |\n"
    "|---|---|---|---|---|---|---|\n"
)
AUTUMN = (
    "## Windows\n\n| Window | Starts | Ends | Live firms |\n|---|---|---|---|\n"
    "| autumn-2027 | 2027-09-01 | 2027-10-20 | |\n\n"
)
CALENDAR = release_windows.load()
# autumn-2027's deadline weeks (deploy/windows.yaml): Sep 13-17, Sep 27 - Oct 1, Oct 11-15.
AUTUMN_ROWS = (
    ("2027-09-01", "2027-09-12", "single"),
    ("2027-09-13", "2027-09-17", "double"),
    ("2027-09-18", "2027-09-26", "single"),
    ("2027-09-27", "2027-10-01", "double"),
    ("2027-10-02", "2027-10-10", "single"),
    ("2027-10-11", "2027-10-15", "double"),
    ("2027-10-16", "2027-10-20", "single"),
)


def _doc(*rows: str, windows: str = WINDOWS, head: str = HEAD) -> str:
    return head + windows + ROTA + "".join(rows) + "\n## After\n"


def _row(
    start: str,
    end: str,
    primary: str = "N",
    backup: str = "AY",
    cover: str = "single",
    window: str = "PW1",
) -> str:
    return f"| {window} | {start} | {end} | {primary} | {backup} | {cover} | |\n"


def _autumn(rows: tuple[tuple[str, str, str], ...] = AUTUMN_ROWS, windows: str = AUTUMN) -> str:
    return _doc(*(_row(a, b, cover=c, window="autumn-2027") for a, b, c in rows), windows=windows)


def test_a_fully_covered_window_passes() -> None:
    assert oc.check(_doc(_row("2027-06-01", "2027-06-03"), _row("2027-06-04", "2027-06-07"))) == []


def test_a_day_without_cover_fails_naming_the_first_one() -> None:
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-03"), _row("2027-06-05", "2027-06-07")))
    assert problems == ["PW1: 1 day(s) without a primary and backup, first 2027-06-04"]


def test_a_day_on_two_rows_fails() -> None:
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-04"), _row("2027-06-04", "2027-06-07")))
    assert problems == ["PW1: 2027-06-04 is on two rota rows"]


@pytest.mark.parametrize(
    ("primary", "backup", "words"),
    [
        ("N", "N", "must not be the primary"),
        ("N", "Sam", "founder handles"),
        ("", "AY", "founder handles"),
    ],
)
def test_the_backup_is_a_different_founder(primary: str, backup: str, words: str) -> None:
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-07", primary, backup)))
    assert any(words in p for p in problems), problems


def test_a_row_outside_its_window_fails() -> None:
    problems = oc.check(_doc(_row("2027-05-31", "2027-06-07")))
    assert any("outside PW1" in p for p in problems)


@pytest.mark.parametrize(
    "contact",
    ["call 512-555-0147 after hours", "page qi@example.test", "(512) 555-0147"],
)
def test_contacts_never_enter_the_file(contact: str) -> None:
    row = _row("2027-06-01", "2027-06-07").replace("| single | |", f"| single | {contact} |")
    problems = oc.check(_doc(row))
    assert any("contacts live in the vault" in p for p in problems), problems


def test_a_firm_named_by_anything_but_a_pilot_code_fails() -> None:
    windows = WINDOWS.replace("PF-A1", "Okonkwo LLP")
    assert any(
        "pilot codes only" in p
        for p in oc.check(_doc(_row("2027-06-01", "2027-06-07"), windows=windows))
    )


def test_the_updated_date_is_required() -> None:
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-07"), head="# On-call\n\n"))
    assert "the frontmatter needs `updated: YYYY-MM-DD`" in problems


def test_a_cover_word_other_than_single_or_double_fails() -> None:
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-07", cover="triple")))
    assert problems == ["line 16: cover is single or double, not 'triple'"]


def test_double_cover_outside_a_release_window_fails() -> None:
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-07", cover="double")), CALENDAR)
    assert problems == ["PW1: double cover is for release-window deadline weeks"]


def test_the_autumn_rota_puts_each_deadline_week_on_double_cover() -> None:
    assert oc.check(_autumn(), CALENDAR) == []


def test_a_deadline_week_day_on_single_cover_fails() -> None:
    rows = (*AUTUMN_ROWS[:3], ("2027-09-27", "2027-10-01", "single"), *AUTUMN_ROWS[4:])
    assert oc.check(_autumn(rows), CALENDAR) == [
        "autumn-2027: deadline-week day 2027-09-27 is not on double cover"
    ]


def test_double_cover_spilling_past_a_deadline_week_fails() -> None:
    rows = (
        AUTUMN_ROWS[0],
        ("2027-09-13", "2027-09-19", "double"),
        ("2027-09-20", "2027-09-26", "single"),
        *AUTUMN_ROWS[3:],
    )
    assert oc.check(_autumn(rows), CALENDAR) == [
        "autumn-2027: 2027-09-18 is on double cover outside a deadline week"
    ]


def test_a_release_rota_window_keeps_the_release_windows_dates() -> None:
    windows = AUTUMN.replace("2027-10-20 |", "2027-10-22 |")
    rows = (*AUTUMN_ROWS[:-1], ("2027-10-16", "2027-10-22", "single"))
    assert oc.check(_autumn(rows, windows), CALENDAR) == [
        "autumn-2027: dates are 2027-09-01 to 2027-10-20 in deploy/windows.yaml"
    ]


@pytest.mark.source_scan
def test_the_committed_rota_covers_pw1_and_the_autumn_window() -> None:
    text = oc.ON_CALL.read_text(encoding="utf-8")
    assert oc.check(text, CALENDAR) == []
    found = {w.name: w for w in oc.windows(text)[0]}
    assert (found["PW1"].starts.isoformat(), found["PW1"].ends.isoformat()) == (
        "2027-06-01",
        "2027-07-12",
    )
    autumn = found["autumn-2027"]
    assert (autumn.starts.isoformat(), autumn.ends.isoformat()) == ("2027-09-01", "2027-10-20")
    shifts = [s for s in oc.shifts(text)[0] if s.window == "autumn-2027"]
    assert {(s.primary, s.backup) for s in shifts} == {("N", "AY")}
    assert [s.cover for s in shifts].count("double") == 3
