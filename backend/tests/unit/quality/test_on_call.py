"""Q-04-T020: every PW1 day has a primary and a named backup, and the rota holds no contacts.

Acceptance: a test page reaches N and escalates to AY after 15 minutes (a paging-tool drill,
recorded in the file), and every PW1 day has a named backup (this check, in check-fast).
"""

from __future__ import annotations

import pytest

from abacus_tools.quality import on_call as oc

HEAD = "---\nupdated: 2027-05-20\n---\n# On-call\n\n"
WINDOWS = (
    "## Windows\n\n| Window | Starts | Ends | Live firms |\n|---|---|---|---|\n"
    "| PW1 | 2027-06-01 | 2027-06-07 | PF-A1 |\n\n"
)
ROTA = "## Rota\n\n| Window | From | To | Primary | Backup | Notes |\n|---|---|---|---|---|---|\n"


def _doc(*rows: str, windows: str = WINDOWS, head: str = HEAD) -> str:
    return head + windows + ROTA + "".join(rows) + "\n## After\n"


def _row(start: str, end: str, primary: str = "N", backup: str = "AY") -> str:
    return f"| PW1 | {start} | {end} | {primary} | {backup} | |\n"


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
    problems = oc.check(_doc(_row("2027-06-01", "2027-06-07").replace("| |", f"| {contact} |")))
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


@pytest.mark.source_scan
def test_the_committed_rota_covers_pw1() -> None:
    text = oc.ON_CALL.read_text(encoding="utf-8")
    assert oc.check(text) == []
    (pw1,) = [w for w in oc.windows(text)[0] if w.name == "PW1"]
    assert (pw1.starts.isoformat(), pw1.ends.isoformat()) == ("2027-06-01", "2027-07-12")
