"""T-06-T24 (TASK-8719; E10; DEC-77): Bluestem's AAA of 1,488,200 split 70/30 per share per day,
distributions never take AAA below zero, and a distribution above AAA routes to the next column
in §1368(c)'s order (AAA, PTI, E&P, OAA, basis)."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.compute.s_corp import aaa_roll, distribute, per_share_per_day

D = Decimal


def test_ac_bluestem_aaa_splits_70_30() -> None:
    split = per_share_per_day(D("1488200"), {"A": (700, 365), "B": (300, 365)})
    assert split == {"A": D("1041740"), "B": D("446460")}
    assert sum(split.values()) == D("1488200")


def test_ac_a_distribution_above_aaa_routes_to_the_next_column() -> None:
    out = distribute(D("1600000"), {"aaa": D("1488200"), "pti": D("50000"), "ep": D("40000")})
    assert out == {
        "aaa": D("1488200"), "pti": D("50000"), "ep": D("40000"), "oaa": D("0"),
        "basis": D("21800"),
    }  # fmt: skip


def test_ac_distributions_never_take_aaa_below_zero() -> None:
    roll = aaa_roll(
        D("100000"), income=D("50000"), losses=D("20000"), nondeductible=D("5000"),
        distributions=D("200000"),
    )  # fmt: skip
    assert roll.before_distributions == D("125000")
    assert (roll.distributions, roll.ending) == (D("125000"), D("0"))
    loss = aaa_roll(D("10000"), income=D("0"), losses=D("30000"), nondeductible=D("0"),
                    distributions=D("5000"))  # fmt: skip
    assert loss.ending == D("-20000") and loss.distributions == D("0")
