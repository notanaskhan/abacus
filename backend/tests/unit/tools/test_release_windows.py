"""Q-04-T002 (SPEC-403 AC-1 to AC-4; Q-04 AC-1.1 to AC-1.4; ADR P-29, DEC-68): the release-window
calendar as code. The committed `deploy/windows.yaml` matches the P-29 rule and §4.9's table; a
firm's window starts with its real data; no live firm leaves every guard inert; a broken file names
its entry."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import yaml

from abacus_tools import release_windows as rw

CT = rw.CT
A1 = "00000000-0000-4000-8000-0000000000a1"
B1 = "00000000-0000-4000-8000-0000000000b1"


def at(text: str) -> datetime:
    """A Central-time instant: "2027-09-01 00:00"."""
    return datetime.fromisoformat(text).replace(tzinfo=CT)


def raw() -> dict[str, Any]:  # Any: a YAML document, edited per test
    return copy.deepcopy(yaml.safe_load(rw.WINDOWS_FILE.read_text(encoding="utf-8")))


def with_firms(*firms: dict[str, Any]) -> rw.Calendar:  # Any: YAML entries
    doc = raw()
    doc["firms"] = list(firms)
    return rw.parse(doc)


PF_A1 = {"tenant_id": A1, "code": "PF-A1", "real_data_since": "2027-06-01", "autumn_window": True}
AUDIT_ONLY = {"tenant_id": B1, "code": "PF-A2", "real_data_since": "2027-06-01"}


# --- the committed file --------------------------------------------------------------------------


def test_the_committed_file_is_valid_and_lists_no_live_firm_yet() -> None:
    cal = rw.load()
    assert [w.id for w in cal.windows] == [
        "autumn-2027",
        "season-2028",
        "autumn-2028",
        "season-2029",
        "autumn-2029",
    ]
    assert cal.firms == ()
    assert rw.main(["check"]) == 0


# §4.9 of the Q-04 spec, as the table prints it.
TABLE = {
    "autumn-2027": (
        "Sep 8-15, Sep 23-30, Oct 8-15",
        "Sep 13-17, Sep 27 - Oct 1, Oct 11-15",
        "Sep 7, Sep 21, Oct 5, Oct 19",
    ),
    "autumn-2028": (
        "Sep 8-15, Sep 25 - Oct 2, Oct 9-16",
        "Sep 11-15, Oct 2-6, Oct 16-20",
        "Sep 5, Sep 19",
    ),
    "autumn-2029": (
        "Sep 10-17, Sep 24 - Oct 1, Oct 8-15",
        "Sep 17-21, Oct 1-5, Oct 15-19",
        "Sep 4",
    ),
    "season-2028": ("—", "Mar 13-17, Apr 17-21", None),
    "season-2029": ("—", "Mar 12-16, Apr 16-20", None),
}


@pytest.mark.parametrize("wid", sorted(TABLE))
def test_ac4_the_calendar_prints_section_4_9(wid: str) -> None:
    cal = rw.load()
    lines = rw.calendar_lines(cal, int(wid[-4:]))
    start = next(i for i, line in enumerate(lines) if line.startswith(wid))
    block = [line.replace(rw.DASH, "-") for line in lines[start : start + 5]]
    minis, weeks, slots = TABLE[wid]
    assert block[1].endswith(minis)
    assert block[2].endswith(weeks)
    if slots is not None:
        assert block[3].endswith(slots)
    assert block[4].endswith("none live yet (guards inert)")


def test_ac4_make_windows_year_2027_prints_the_three_mini_freezes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert rw.main(["calendar", "--year", "2027"]) == 0
    out = capsys.readouterr().out.replace(rw.DASH, "-")
    assert "mini-freezes:   Sep 8-15, Sep 23-30, Oct 8-15" in out
    assert "2028" not in out


@pytest.mark.parametrize(
    ("year", "skipped"), [(2028, ["Mar 14", "Apr 18"]), (2029, ["Mar 13", "Apr 17"])]
)
def test_season_slots_are_every_tuesday_but_the_deadline_weeks(
    year: int, skipped: list[str]
) -> None:
    cal = rw.load()
    window = next(w for w in cal.windows if w.id == f"season-{year}")
    days = rw.slots(cal, window)
    assert all(d.weekday() == 1 for d in days)
    tuesdays = [
        window.span.start + timedelta(days=i)
        for i in range((window.span.end - window.span.start).days + 1)
        if (window.span.start + timedelta(days=i)).weekday() == 1
    ]
    missing = [f"{d.strftime('%b')} {d.day}" for d in tuesdays if d not in days]
    assert missing == skipped


# --- the P-29 rule -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("deadline", "due"),
    [
        (date(2027, 9, 15), date(2027, 9, 15)),  # Wed
        (date(2028, 4, 15), date(2028, 4, 18)),  # Sat; Emancipation Day observed Mon Apr 17
        (date(2029, 4, 15), date(2029, 4, 17)),  # Sun -> Mon Apr 16, Emancipation Day -> Tue
        (date(2028, 9, 30), date(2028, 10, 2)),  # Sat -> Mon
        (date(2028, 10, 15), date(2028, 10, 16)),  # Sun -> Mon (Columbus Day was Oct 9)
        (date(2029, 10, 15), date(2029, 10, 15)),  # Mon, not Columbus Day (Oct 8)
        (date(2027, 4, 15), date(2027, 4, 15)),  # Thu; Emancipation Day Fri Apr 16
        (date(2030, 10, 14), date(2030, 10, 15)),  # Columbus Day itself
    ],
)
def test_deadlines_shift_past_weekends_and_legal_holidays(deadline: date, due: date) -> None:
    assert rw.shifted(deadline) == due


def test_a_mini_freeze_is_eight_days_ending_on_the_shifted_deadline() -> None:
    for window in rw.load().windows:
        if window.kind == "season":
            assert window.mini_freezes == ()
            continue
        for span, week in zip(window.mini_freezes, window.deadline_weeks, strict=True):
            assert (span.end - span.start).days == 7
            assert span.end in week


# --- AC-1: a firm's window starts with its real data ---------------------------------------------


def test_ac1_an_ebp_firm_is_in_autumn_2027_from_sep_1_midnight_ct() -> None:
    cal = with_firms(PF_A1, AUDIT_ONLY)
    assert rw.in_window(cal, "PF-A1", at("2027-09-01 00:00")) == "autumn-2027"
    assert rw.in_window(cal, "PF-A1", at("2027-08-31 23:59")) is None
    assert rw.in_window(cal, "PF-A1", at("2027-10-20 23:59")) == "autumn-2027"
    assert rw.in_window(cal, "PF-A1", at("2027-10-21 00:00")) is None
    # Midnight in Chicago is still Aug 31 in UTC terms the other way round: the day is Central.
    assert rw.in_window(cal, A1, datetime.fromisoformat("2027-09-01T04:59:00+00:00")) is None
    assert rw.in_window(cal, A1, datetime.fromisoformat("2027-09-01T05:00:00+00:00")) == (
        "autumn-2027"
    )


def test_ac1_an_audit_only_firm_waits_for_the_season_window() -> None:
    cal = with_firms(PF_A1, AUDIT_ONLY)
    assert rw.in_window(cal, "PF-A2", at("2027-09-15 12:00")) is None
    assert rw.in_window(cal, "PF-A2", at("2027-12-31 23:59")) is None
    assert rw.in_window(cal, "PF-A2", at("2028-01-01 00:00")) == "season-2028"


def test_a_firm_not_live_until_after_a_window_starts_joins_it_on_its_day() -> None:
    late = {**PF_A1, "real_data_since": "2027-09-20"}
    cal = with_firms(late)
    assert rw.in_window(cal, "PF-A1", at("2027-09-19 12:00")) is None
    assert rw.in_window(cal, "PF-A1", at("2027-09-20 00:00")) == "autumn-2027"


def test_ac2_with_no_live_firm_every_guard_is_inert() -> None:
    cal = with_firms({**PF_A1, "real_data_since": None})
    wed = at("2027-09-15 12:00")  # a deadline day, mini-freeze, not a slot
    assert rw.in_window(cal, "PF-A1", wed) is None
    assert rw.platform_window(cal, wed) is None
    assert rw.deadline_week(cal, wed) is None
    assert rw.mini_freeze(cal, wed) is None
    assert rw.flip_slot(cal, wed) is True
    assert rw.migrate_not_before(cal, wed) == wed
    committed = rw.load()
    assert rw.platform_window(committed, wed) is None


# --- platform rules, flips and migrations --------------------------------------------------------


def test_platform_rules_follow_any_live_firm_and_flip_rules_each_firm() -> None:
    cal = with_firms(PF_A1, AUDIT_ONLY)
    wed = at("2027-09-15 12:00")
    assert rw.platform_window(cal, wed) == "autumn-2027"
    assert rw.deadline_week(cal, wed) == rw.Span(date(2027, 9, 13), date(2027, 9, 17))
    assert rw.mini_freeze(cal, wed, "PF-A1") == rw.Span(date(2027, 9, 8), date(2027, 9, 15))
    # The audit-only firm is outside its window: no deadline week, no slot rule for its flips.
    assert rw.deadline_week(cal, wed, "PF-A2") is None
    assert rw.flip_slot(cal, wed, "PF-A2") is True


@pytest.mark.parametrize(
    ("when", "slot"),
    [
        ("2027-09-07 19:00", True),  # the first in-window slot
        ("2027-09-07 18:59", False),
        ("2027-09-07 20:59", True),
        ("2027-09-07 21:00", False),
        ("2027-09-14 19:30", False),  # mini-freeze and deadline week: no slot (AC-4.2)
        ("2027-09-21 19:30", True),
        ("2027-09-28 19:30", False),  # deadline week Sep 27 - Oct 1
        ("2027-10-19 19:30", True),
        ("2027-09-09 19:30", False),  # a Thursday
    ],
)
def test_the_tuesday_slot_inside_a_window(when: str, slot: bool) -> None:
    cal = with_firms(PF_A1)
    assert rw.flip_slot(cal, at(when), "PF-A1") is slot
    assert rw.flip_slot(cal, at(when)) is slot


def test_migrations_wait_for_8_pm_ct_inside_a_window() -> None:
    cal = with_firms(PF_A1)
    assert rw.migrate_not_before(cal, at("2027-09-21 19:05")) == at("2027-09-21 20:00")
    assert rw.migrate_not_before(cal, at("2027-09-21 20:30")) == at("2027-09-21 20:30")
    outside = at("2027-11-04 10:00")
    assert rw.migrate_not_before(cal, outside) == outside


def test_a_naive_instant_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        rw.in_window(rw.load(), "PF-A1", datetime(2027, 9, 1))


# --- AC-3: check-fast names a broken entry -------------------------------------------------------


def broken(edit: Callable[[dict[str, Any]], None]) -> list[str]:  # Any: YAML
    doc = raw()
    edit(doc)
    with pytest.raises(rw.WindowsError) as caught:
        rw.parse(doc)
    return caught.value.problems


def test_ac3_an_overlapping_window_fails() -> None:
    def edit(doc: dict[str, Any]) -> None:  # Any: YAML
        doc["windows"][0]["ends"] = date(2028, 1, 5)

    problems = broken(edit)
    assert any("windows[season-2028]: overlaps autumn-2027" in p for p in problems)


def test_ac3_an_undated_mini_freeze_fails() -> None:
    def edit(doc: dict[str, Any]) -> None:  # Any: YAML
        doc["windows"][0]["mini_freezes"][1] = [date(2027, 9, 23)]

    assert any("windows[autumn-2027].mini_freezes[1]: undated" in p for p in broken(edit))


def test_ac3_a_freeze_that_differs_from_the_rule_fails() -> None:
    def edit(doc: dict[str, Any]) -> None:  # Any: YAML
        doc["windows"][2]["deadline_weeks"][1] = [date(2028, 9, 25), date(2028, 9, 29)]

    assert any(
        "windows[autumn-2028].deadline_weeks: differ from the P-29 rule" in p for p in broken(edit)
    )


def test_ac3_a_tenant_without_a_code_fails() -> None:
    def edit(doc: dict[str, Any]) -> None:  # Any: YAML
        doc["firms"] = [{"tenant_id": A1, "real_data_since": "2027-06-01"}]

    assert any(f"({A1}): a tenant without a pilot code" in p for p in broken(edit))


@pytest.mark.parametrize("code", ["Northwind", "PF-a1", "PF-A", "Brightwater Hale", "PF-A1x"])
def test_ac3_a_code_that_is_not_a_pilot_code_fails(code: str) -> None:
    def edit(doc: dict[str, Any]) -> None:  # Any: YAML
        doc["firms"] = [{"tenant_id": A1, "code": code, "real_data_since": "2027-06-01"}]

    assert any("is not a pilot code" in p for p in broken(edit))


@pytest.mark.parametrize("code", ["PF-A1", "PF-T1", "PF-C12", "PC28-07"])
def test_pilot_and_cohort_codes_pass(code: str) -> None:
    cal = with_firms({"tenant_id": A1, "code": code, "real_data_since": "2027-06-01"})
    assert cal.firm(code) is not None


def test_a_firm_listed_twice_and_an_unknown_key_fail() -> None:
    def edit(doc: dict[str, Any]) -> None:  # Any: YAML
        doc["firms"] = [PF_A1, {**PF_A1, "tenant_id": str(uuid4())}]
        doc["releases"] = []

    problems = broken(edit)
    assert any("(PF-A1): listed twice" in p for p in problems)
    assert any("unknown keys ['releases']" in p for p in problems)


def test_check_exits_1_and_names_each_problem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = raw()
    doc["firms"] = [{"tenant_id": A1, "code": "Acme Pension Plan"}]
    path = tmp_path / "windows.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert rw.main(["--file", str(path), "check"]) == 1
    assert "is not a pilot code" in capsys.readouterr().err


def test_the_cli_answers_in_window_and_slot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = raw()
    doc["firms"] = [PF_A1]
    path = tmp_path / "windows.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert (
        rw.main(
            [
                "--file",
                str(path),
                "in-window",
                "--firm",
                "PF-A1",
                "--at",
                "2027-09-01T00:00:00-05:00",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "autumn-2027"
    assert rw.main(["--file", str(path), "slot", "--at", "2027-09-14T19:30:00-05:00"]) == 2
    assert capsys.readouterr().out.strip() == "no slot"
