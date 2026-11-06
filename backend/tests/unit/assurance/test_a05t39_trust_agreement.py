"""A-05-T39 (TASK-3306; DEC-2305): the trust agreement engine and the sign-off hold, from the row.

"Six funds foot to 14,895,000 and 12,683,000, the Unadjusted layer shows a 0.00 receivable and
16,812,400, and Sign off answers 409 certification_unevaluated until every point is evaluated."
"""

from __future__ import annotations

import uuid
from decimal import Decimal as D

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import ebp_investments
from abacus.modules.assurance.compute.ebp.trust_agreement import TbFigure, TrustLine, agree

_FUNDS = (
    ("f1", "Vanguard 500", "5000000.00", "4100000.00"),
    ("f2", "Vanguard Total Bond", "2500000.00", "2200000.00"),
    ("f3", "Fidelity Growth", "2395000.00", "2050000.00"),
    ("f4", "American Funds EuroPac", "2000000.00", "1733000.00"),
    ("f5", "T. Rowe Target 2040", "1500000.00", "1400000.00"),
    ("f6", "Stable Value", "1500000.00", "1200000.00"),
)


def _tenant() -> TenantContext:
    return TenantContext(uuid.uuid4(), "system", "test")


def _trust() -> list[TrustLine]:
    lines = [TrustLine(k, n, D(b), D(e), "level1") for k, n, e, b in _FUNDS]
    lines.append(
        TrustLine("sdba", "Self-directed brokerage", D("1257000.00"), D("1605000.00"), "nav")
    )
    lines.append(
        TrustLine("notes", "Notes receivable from participants", D("288500.00"), D("312400.00"),
                  "not_certified")
    )  # fmt: skip
    return lines


def _tb() -> list[TbFigure]:
    return [TbFigure(t.fund_name, t.boy, t.eoy or D(0)) for t in _trust()]


def test_ac_six_funds_foot_for_both_dates() -> None:
    funds = [t for t in _trust() if t.line_key.startswith("f")]
    assert sum((t.eoy or D(0) for t in funds), D(0)) == D("14895000.00")
    assert sum((t.boy or D(0) for t in funds), D(0)) == D("12683000.00")
    found = agree(_trust(), _tb())
    assert found.investments_eoy == D("16500000.00")
    assert found.investments_boy == D("13940000.00")
    assert all(line.ties for line in found.lines)
    assert found.py_ties


def test_ac_notes_receivable_sit_below_and_are_not_certified() -> None:
    found = agree(_trust(), _tb())
    assert found.below_eoy == D("312400.00")
    assert found.level1_eoy + found.nav_eoy == found.investments_eoy


def test_ac_a_line_that_disagrees_is_off_by_its_difference() -> None:
    tb = [
        TbFigure(f.name, f.boy, f.eoy - D("100.00") if f.name == "Stable Value" else f.eoy)
        for f in _tb()
    ]
    off = {a.fund_name: a for a in agree(_trust(), tb).lines}["Stable Value"]
    assert not off.ties
    assert off.off_by == D("100.00")


def test_ac_a_missing_tb_line_does_not_tie() -> None:
    found = agree(_trust(), _tb()[1:])
    assert not {a.fund_name: a for a in found.lines}["Vanguard 500"].ties


@pytest.mark.asyncio
async def test_ac_sign_off_is_held_without_a_work_item() -> None:
    held = await ebp_investments.sign_off_guard(_tenant(), uuid.uuid4(), None)
    assert held == (ebp_investments.UNEVALUATED, len(ebp_investments.POINT_KEYS))


def test_ac_a_level_with_no_subtotal_still_counts_in_the_investments() -> None:
    found = agree([TrustLine("x", "Other fund", None, D("100.00"), "level2")], [])
    assert (found.investments_eoy, found.level1_eoy, found.nav_eoy) == (D("100.00"), D(0), D(0))
