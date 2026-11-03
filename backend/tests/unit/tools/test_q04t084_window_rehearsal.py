"""Q-04-T084, T085 (DEC-2081): the window rehearsal runs the real P-29 gate on the synthetic firm.

The rehearsal treats PF-X1 as live in memory only; `deploy/windows.yaml` keeps it synthetic, so on
the real calendar every guard stays inert (DEC-68).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from abacus_tools import release_windows, window_rehearsal

LIVE = date(2027, 8, 2)


def _cal() -> release_windows.Calendar:
    return window_rehearsal.as_live(release_windows.load(), "PF-X1", LIVE)


def test_the_real_calendar_keeps_pf_x1_synthetic_and_every_guard_inert() -> None:
    real = release_windows.load()
    assert [f.synthetic for f in real.firms if f.code == "PF-X1"] == [True]
    slot = datetime.fromisoformat("2027-10-05T19:05-05:00")
    assert release_windows.platform_window(real, slot) is None
    assert window_rehearsal.read(real, slot).bare == ()


def test_only_a_synthetic_firm_is_rehearsed() -> None:
    with pytest.raises(SystemExit, match="not a synthetic firm"):
        window_rehearsal.as_live(release_windows.load(), "PF-A1", LIVE)


def test_t084_the_oct_5_slot_promotes_a_defect_only_release_with_a_rollback() -> None:
    r = window_rehearsal.read(_cal(), datetime.fromisoformat("2027-10-05T19:05-05:00"))
    assert (r.window, r.tuesday_slot, r.deadline_week) == ("autumn-2027", True, None)
    assert r.bare == ("window_mode_missing", "rollback_missing")
    assert r.defect_only == ()


@pytest.mark.parametrize("at", ["2027-10-05T15:00-05:00", "2027-10-06T19:05-05:00"])
def test_t084_outside_the_slot_a_promotion_waits(at: str) -> None:
    r = window_rehearsal.read(_cal(), datetime.fromisoformat(at))
    assert r.defect_only == ("outside_the_tuesday_slot",)
    assert r.hotfix == ()


@pytest.mark.parametrize("day", [11, 12, 13, 14, 15])
def test_t085_every_day_of_the_oct_11_to_15_week_refuses_a_promotion_without_a_hotfix(
    day: int,
) -> None:
    r = window_rehearsal.read(_cal(), datetime.fromisoformat(f"2027-10-{day:02d}T19:05-05:00"))
    assert r.deadline_week == "2027-10-11/2027-10-15"
    assert r.defect_only == ("deadline_week_without_hotfix",)
    assert not r.flip_slot


def test_the_table_reads_each_instant_and_writes_markdown(tmp_path: Path) -> None:
    out = tmp_path / "r.md"
    assert (
        window_rehearsal.main(
            [
                "--firm",
                "PF-X1",
                "--live-since",
                "2027-08-02",
                "--at",
                "2027-10-05T19:05-05:00",
                "--md",
                str(out),
            ]
        )
        == 0
    )
    text = out.read_text()
    assert "| 2027-10-05T19:05:00-05:00 | autumn-2027 |" in text
    assert "refused: window_mode_missing, rollback_missing | promotes | promotes |" in text
