# ac-test-author: ayushkbhatia
"""Q-04-T012 (TASK-1744; ADR-078 independent; c05 = Q-04-T005; SPEC-403 AC-10; Q-04 AC-3.1,
AC-3.3; DEC-834): the flag calendar, from the spec and `deploy/windows.yaml`, not from T005's own
suite.

Acceptance (the task row, c05's share): the rules hold on their edges and the suite fails when one
is weakened. Here: every window's first and last day (and a season's trailing deadline week) is
inside, the day either side is not; an exception needs a 1-200 character reason and a handle
that is not the owner's, and nothing else; `--check` exits 1 naming flag, date and window; the
calendar lists each registered flag once, by expiry, with its last train strictly before expiry,
warns at 21 days but not 22, and says "none left" when no train remains.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import yaml

from abacus_tools import release_windows
from abacus_tools.codegen import feature_flags as ff
from abacus_tools.codegen.feature_flags import RegistryError, parse

OWNER = "notanaskhan"
OTHER = "ayushkbhatia"


def _flag(expires: date, **over: object) -> str:
    created = expires - timedelta(days=30)  # inside the 90-day lifetime
    item: dict[str, object] = {
        "name": "pilots.independent_probe",
        "description": "Independent probe flag",
        "owner": OWNER,
        "created": created,
        "expires": expires,
        "kind": "boolean",
        "default": False,
        **over,
    }
    return yaml.safe_dump({"flags": [item]})


def _cal() -> release_windows.Calendar:
    return release_windows.load()


# --- Window edges (SPEC-403 AC-10) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("expires", "window"),
    [
        (date(2027, 8, 31), None),
        (date(2027, 9, 1), "autumn-2027"),  # first day
        (date(2027, 10, 20), "autumn-2027"),  # last day
        (date(2027, 10, 21), None),
        (date(2027, 12, 31), None),
        (date(2028, 1, 1), "season-2028"),  # first day
        (date(2028, 4, 20), "season-2028"),  # last day
        (date(2028, 4, 21), "season-2028"),  # the trailing deadline week (Apr 17-21)
        (date(2028, 4, 22), None),
    ],
)
def test_c05_a_window_holds_its_first_and_last_days_and_not_the_days_beside(
    expires: date, window: str | None
) -> None:
    problems = ff.window_conflicts(parse(_flag(expires)), _cal())
    if window is None:
        assert problems == []
    else:
        assert len(problems) == 1
        assert f"pilots.independent_probe expires on {expires}, inside {window}" in problems[0]


def test_c05_the_committed_windows_file_is_the_calendar_read() -> None:
    ids = [w.id for w in _cal().windows]
    assert ids[:2] == ["autumn-2027", "season-2028"]


# --- The exception -------------------------------------------------------------------------------


def test_c05_an_exception_by_the_other_founder_clears_the_conflict_and_is_marked() -> None:
    entries = parse(
        _flag(date(2027, 9, 10), window_exception={"reason": "x" * 200, "approved_by": OTHER})
    )
    assert ff.window_conflicts(entries, _cal()) == []
    [row] = ff.flag_calendar(entries, _cal(), today=date(2027, 8, 1))
    assert (row.window, row.excepted) == ("autumn-2027", True)


@pytest.mark.parametrize(
    "exception",
    [
        {"reason": "Renewal", "approved_by": OWNER},  # self-approval
        {"reason": "x" * 201, "approved_by": OTHER},
        {"reason": "   ", "approved_by": OTHER},
        {"reason": "Renewal"},
        {"reason": "Renewal", "approved_by": OTHER, "until": "2027-09-30"},  # an extra key
        {"reason": "Renewal", "approved_by": "not a handle!"},
        ["Renewal", OTHER],
    ],
)
def test_c05_a_weakened_exception_is_refused(exception: object) -> None:
    with pytest.raises(RegistryError, match="window_exception"):
        parse(_flag(date(2027, 9, 10), window_exception=exception))


def test_c05_an_exception_outside_any_window_is_harmless() -> None:
    entries = parse(
        _flag(date(2027, 8, 31), window_exception={"reason": "Belt", "approved_by": OTHER})
    )
    assert ff.window_conflicts(entries, _cal()) == []


def test_c05_check_exits_1_naming_flag_date_and_window(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def source(_directory: object = None) -> str:
        return _flag(date(2028, 4, 21))

    def expired(_entries: list[ff.Entry], _today: date | None = None) -> list[ff.Entry]:
        return []

    monkeypatch.setattr(ff, "source", source)
    monkeypatch.setattr(ff, "expired", expired)
    assert ff.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "pilots.independent_probe" in err
    assert "2028-04-21" in err
    assert "season-2028" in err


# --- The calendar --------------------------------------------------------------------------------


def test_c05_every_registered_flag_is_listed_once_by_expiry_with_a_train_before_it() -> None:
    entries = parse(ff.source())
    rows = ff.flag_calendar(entries, _cal(), today=date(2026, 10, 29))
    names = [r.name for r in rows]
    assert sorted(names) == sorted(e.name for e in entries)
    assert len(names) == len(set(names))
    assert [(r.expires, r.name) for r in rows] == sorted((r.expires, r.name) for r in rows)
    for r in rows:
        assert r.last_train is not None, r.name
        assert date(2026, 10, 29) <= r.last_train < r.expires, r.name


@pytest.mark.parametrize(("days_left", "warn"), [(22, False), (21, True), (0, True)])
def test_c05_the_warning_starts_at_21_days(days_left: int, warn: bool) -> None:
    expires = date(2027, 8, 31)
    [row] = ff.flag_calendar(parse(_flag(expires)), _cal(), today=expires - timedelta(days_left))
    assert row.warn is warn
    line = ff.calendar_lines([row])[1]
    assert line.endswith("! renew or retire") is warn


def test_c05_a_flag_with_no_train_left_says_so() -> None:
    expires = date(2027, 8, 6)  # a Friday; the last Thursday train is the day before
    [row] = ff.flag_calendar(parse(_flag(expires)), _cal(), today=expires)
    assert row.last_train is None
    assert "none left" in ff.calendar_lines([row])[1]
    [earlier] = ff.flag_calendar(parse(_flag(expires)), _cal(), today=date(2027, 8, 5))
    assert earlier.last_train == date(2027, 8, 5)


def test_c05_a_conflict_without_an_exception_reads_conflict_in_the_calendar() -> None:
    [row] = ff.flag_calendar(parse(_flag(date(2027, 9, 1))), _cal(), today=date(2027, 8, 1))
    assert row.window == "autumn-2027"
    assert row.excepted is False
    assert "autumn-2027 CONFLICT" in ff.calendar_lines([row])[1]
