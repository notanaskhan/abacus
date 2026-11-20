"""Q-04-T230 (S52; TASK-8858): autumn-2028 is recorded closed on Oct 20 in deploy/windows.yaml;
a `closed` date before the window's last day (its end or a deadline week past it) is refused; the
record changes no guard."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest
import yaml

from abacus_tools import release_windows as rw


def _raw() -> dict[str, Any]:  # Any: a YAML document, edited per test
    return yaml.safe_load(rw.WINDOWS_FILE.read_text(encoding="utf-8"))


def _autumn_2028(doc: dict[str, Any]) -> dict[str, Any]:
    return next(w for w in doc["windows"] if w["id"] == "autumn-2028")


def test_autumn_2028_is_closed_on_oct_20() -> None:
    window = next(w for w in rw.load().windows if w.id == "autumn-2028")
    assert window.closed == date(2028, 10, 20)


@pytest.mark.parametrize("closed", ["2028-10-19", "not a date"])
def test_a_close_before_the_last_day_is_refused(closed: str) -> None:
    doc = copy.deepcopy(_raw())
    _autumn_2028(doc)["closed"] = date.fromisoformat(closed) if closed[0] == "2" else closed
    with pytest.raises(rw.WindowsError, match=r"autumn-2028\]\.closed"):
        rw.parse(doc)


def test_the_close_record_changes_no_guard() -> None:
    doc = copy.deepcopy(_raw())
    _autumn_2028(doc).pop("closed")
    open_cal, closed_cal = rw.parse(doc), rw.load()
    for day in (date(2028, 10, 16), date(2028, 10, 20), date(2028, 10, 24)):
        assert [w.covers(day) for w in open_cal.windows] == [
            w.covers(day) for w in closed_cal.windows
        ]
