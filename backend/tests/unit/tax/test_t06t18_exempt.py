"""T-06-T18 (SPEC-702; DEC-5629): E12 on Lakeshore Literacy Alliance's 990 (TXP-13 c)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.compute import exempt as e12

D = Decimal


def test_lakeshore_part_ix_foots_to_4_014_000_with_an_80_0_program_ratio() -> None:
    lines = [
        e12.direct("1", "Program grants", D("3210000"), "program"),
        e12.direct("11", "Management and general", D("486000"), "management_general"),
        e12.direct("12", "Fundraising", D("318000"), "fundraising"),
    ]
    ix = e12.part_ix(lines)
    assert (ix.program, ix.management_general, ix.fundraising, ix.total) == (
        D("3210000"), D("486000"), D("318000"), D("4014000"),
    )  # fmt: skip
    assert ix.program_ratio == D("80.0")


def test_a_time_study_line_crossfoots_by_largest_remainder() -> None:
    pct: dict[e12.Column, Decimal] = {
        "program": D("70"),
        "management_general": D("20"),
        "fundraising": D("10"),
    }
    ln = e12.time_study("7", "Other salaries", D("100001"), pct)
    assert ln.crossfoots
    assert (ln.program, ln.management_general, ln.fundraising) == (
        D("70001"),
        D("20000"),
        D("10000"),
    )
    with pytest.raises(ValueError, match="sum to 100"):
        e12.time_study("7", "x", D("1"), {"program": D("90")})


def test_public_support_threshold_is_one_third() -> None:
    assert e12.public_support(D("1"), D("3")).met
    assert not e12.public_support(D("33332"), D("100000")).met
    assert e12.public_support(D("874"), D("1000")).pct == D("87.4")


def test_a_line_that_does_not_crossfoot_is_refused() -> None:
    bad = e12.ExpenseLine("1", "x", D("10"), D("5"), D("4"), D("0"), "direct")
    with pytest.raises(ValueError, match="crossfoot"):
        e12.part_ix([bad])
