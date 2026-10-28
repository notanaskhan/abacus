"""Q-04-T005 (SPEC-403 AC-10; Q-04 AC-3.1, AC-3.3; P-29; RK-15): the flag renewal calendar. A flag
expiring Sep 10, 2027 without `window_exception` fails `feature_flags --check`; with one
approved by the other founder it passes and the calendar marks it; `make flag-calendar` lists
every registered flag with its last release train before expiry and warns within 21 days."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest
import yaml

from abacus_tools import release_windows
from abacus_tools.codegen import feature_flags as ff
from abacus_tools.codegen.feature_flags import RegistryError, parse


def entry(**over: object) -> str:
    base: dict[str, object] = {
        "name": "sampling.sample_sets",
        "description": "Sample sets for PW1",
        "owner": "notanaskhan",
        "created": date(2027, 6, 14),
        "expires": date(2027, 9, 10),
        "kind": "boolean",
        "default": False,
        **over,
    }
    return yaml.safe_dump({"flags": [base]})


def calendar(live: bool = False) -> release_windows.Calendar:
    doc: dict[str, Any] = copy.deepcopy(  # Any: the YAML document
        yaml.safe_load(release_windows.WINDOWS_FILE.read_text(encoding="utf-8"))
    )
    if live:
        doc["firms"] = [
            {
                "tenant_id": "00000000-0000-4000-8000-0000000000a1",
                "code": "PF-A1",
                "real_data_since": "2027-06-01",
                "autumn_window": True,
            }
        ]
    return release_windows.parse(doc)


def test_ac10_a_flag_expiring_sep_10_2027_without_an_exception_fails_with_the_window_named() -> (
    None
):
    problems = ff.window_conflicts(parse(entry()), calendar())
    assert len(problems) == 1
    assert "sampling.sample_sets expires on 2027-09-10, inside autumn-2027" in problems[0]


def test_ac10_an_exception_approved_by_the_other_founder_passes_and_is_marked() -> None:
    entries = parse(
        entry(window_exception={"reason": "Registry-only renewal", "approved_by": "ayushkbhatia"})
    )
    assert ff.window_conflicts(entries, calendar()) == []
    [row] = ff.flag_calendar(entries, calendar(), today=date(2027, 8, 1))
    assert (row.window, row.excepted) == ("autumn-2027", True)
    assert "autumn-2027 (excepted)" in ff.calendar_lines([row])[1]


@pytest.mark.parametrize(
    "exception",
    [
        {"reason": "Renewal", "approved_by": "notanaskhan"},  # the owner
        {"reason": "", "approved_by": "ayushkbhatia"},
        {"approved_by": "ayushkbhatia"},
        {"reason": "Renewal", "approved_by": "Ayush K"},
        "both founders said so",
    ],
)
def test_ac10_a_window_exception_names_a_reason_and_the_other_founder(exception: object) -> None:
    with pytest.raises(RegistryError, match="window_exception"):
        parse(entry(window_exception=exception))


def test_expiry_outside_every_window_needs_no_exception() -> None:
    assert ff.window_conflicts(parse(entry(expires=date(2027, 8, 31))), calendar()) == []
    later = entry(created=date(2027, 8, 1), expires=date(2027, 10, 21))
    assert ff.window_conflicts(parse(later), calendar()) == []
    last = entry(created=date(2027, 8, 1), expires=date(2027, 10, 20))
    assert ff.window_conflicts(parse(last), calendar()) != []


@pytest.mark.parametrize("journeys", [["j04-fs-audit", "j02-client-onboarding"], ["j19"]])
def test_journeys_are_distinct_spec_slugs(journeys: list[str]) -> None:
    [e] = parse(entry(expires=date(2027, 8, 31), journeys=journeys))
    assert e.journeys == tuple(journeys)


@pytest.mark.parametrize("journeys", [[], ["J04 FS audit"], ["j04", "j04"], "j04"])
def test_bad_journeys_are_refused(journeys: object) -> None:
    with pytest.raises(RegistryError, match="journeys"):
        parse(entry(expires=date(2027, 8, 31), journeys=journeys))


def test_outside_windows_the_train_is_thursday() -> None:
    days = ff.train_days(calendar(), date(2026, 11, 2), date(2026, 11, 20))
    assert days == [date(2026, 11, 5), date(2026, 11, 12), date(2026, 11, 19)]


def test_inside_a_live_window_the_train_is_the_tuesday_slot() -> None:
    days = ff.train_days(calendar(live=True), date(2027, 8, 23), date(2027, 10, 1))
    assert days == [date(2027, 8, 26), date(2027, 9, 7), date(2027, 9, 21)]


def test_ac10_flag_calendar_lists_every_registered_flag_with_its_last_train() -> None:
    entries = parse(ff.source())
    rows = ff.flag_calendar(entries, release_windows.load(), today=date(2026, 10, 28))
    assert {r.name for r in rows} == {e.name for e in entries}
    assert all(r.last_train is not None and r.last_train < r.expires for r in rows)
    assert all(r.last_train is not None and r.last_train.weekday() == 3 for r in rows)
    lines = ff.calendar_lines(rows)
    assert lines[-1] == f"{len(rows)} flags; 0 expire within 21 days"


def test_the_21_day_warning() -> None:
    entries = parse(entry(expires=date(2027, 8, 31)))
    [soon] = ff.flag_calendar(entries, calendar(), today=date(2027, 8, 10))
    [later] = ff.flag_calendar(entries, calendar(), today=date(2027, 8, 9))
    assert (soon.warn, later.warn) == (True, False)
    assert ff.calendar_lines([soon])[1].endswith("! renew or retire")


def test_check_fails_and_names_the_window(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def source(_directory: object = None) -> str:
        return entry()

    def expired(_entries: list[ff.Entry], _today: date | None = None) -> list[ff.Entry]:
        return []

    monkeypatch.setattr(ff, "source", source)
    monkeypatch.setattr(ff, "expired", expired)
    assert ff.main(["--check"]) == 1
    assert "inside autumn-2027" in capsys.readouterr().err


def test_the_committed_registry_passes_the_window_check() -> None:
    assert ff.window_conflicts(parse(ff.source()), release_windows.load()) == []
