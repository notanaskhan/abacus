"""Q-04-T054: the M12 pack's reads from files and its W6/W7 colours, without a database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from abacus.modules.platform.api import PilotSnapshot
from abacus_tools import m12_pack

D = Decimal


def test_the_s21_reserve_is_its_three_support_rows() -> None:
    assert m12_pack.reserve_task_equivalents("21") == D("6.00")  # 1.5 + 1.75 + 2.75


@pytest.mark.parametrize(
    ("value", "baseline", "week", "expected"),
    [
        (D("-3"), 10, 2, "green"),  # 30% faster
        (D("-1"), 10, 2, "amber"),  # 10% faster
        (D("2"), 10, 3, "amber"),  # slower, before week 8
        (D("2"), 10, 8, "red"),
        (D("2"), None, 8, "no data"),
    ],
)
def test_w6_is_the_share_faster_than_baseline(
    value: Decimal, baseline: int | None, week: int, expected: str
) -> None:
    snap = PilotSnapshot(uuid4(), "w6_vs_baseline_days.v1", value, baseline)
    assert m12_pack.w6_colour(m12_pack.w6_faster(snap), week) == expected


def test_w7_over_15_percent_stays_amber_in_a_weekly_read() -> None:
    assert m12_pack.w7_colour(D("0.08")) == "green"
    assert m12_pack.w7_colour(D("0.12")) == "amber"
    assert m12_pack.w7_colour(D("0.30")) == "amber"


def test_support_hours_against_the_reserve_and_rk07(tmp_path: Path) -> None:
    log = tmp_path / "support-hours.csv"
    log.write_text(
        "sprint,week,lane,hours,sev1,sev2,sev3\n"
        "20,2027-08-02,AY,30,0,1,2\n21,2027-08-09,N,20,0,0,1\n21,2027-08-16,AY,20,1,0,0\n",
        encoding="utf-8",
    )
    found = m12_pack.support(["20", "21"], D(6), log)
    assert [(s.sprint, s.hours, s.reserve_hours, s.over) for s in found] == [
        ("20", D(30), D("16.50"), True),  # (1.75 + 1) x 6
        ("21", D(40), D("36.00"), True),
    ]
    assert found[1].sev == (1, 0, 1)
    assert m12_pack.rk07(found) is True
    log.write_text("sprint,hours\n21,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        m12_pack.support(["21"], D(6), log)


def test_escaped_defects_inside_the_weeks_read() -> None:
    found = m12_pack.defects_found(date(2026, 10, 23), date(2026, 10, 23))
    assert ("ED-001", "SEV4", "fixed") in found
    assert all(i.startswith("ED-") for i, _, _ in found)


def test_the_test_firms_dossier_is_quoted_not_estimated() -> None:
    level, _lines = m12_pack.dossier_lines("PF-X1")
    assert level != "no dossier"
    assert m12_pack.dossier_lines("PF-NONE") == ("no dossier", [])
