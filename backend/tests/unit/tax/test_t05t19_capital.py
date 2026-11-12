"""T-05-T19 (TASK-7406; T-05 §4.4 E7, F7; DEC-4405): E7 capital and Schedule M-2 on the Ridgeline
figures (T-05 §1): 5,960,000 + 250,000 + 1,256,200 - 600,000 = 6,866,200; the transfer of 5 of
Pell Street Ventures' 35 points at 6/30 moves 331,405 = 2,319,835 x 5/35 in all three bases; the
tax column omits the 6,200 tax-exempt interest until the 9:51 fix (M-2 off 6,200), after which
124 + 2,356 + 2,015 + 155 + 1,550 = 6,200 and line 9 = 6,866,200; the §743(b) placeholder is
28,595 = 360,000 - 331,405."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.tax.compute.entity.capital import (
    BASES,
    CapitalInvalid,
    CapitalPartner,
    Movements,
    Transfer,
    capital,
)

D = Decimal
L21 = D(6_866_200)
TAX_EXEMPT = {"ashford": 124, "shah": 2_356, "psv": 2_015, "ps2": 155, "dumont": 1_550}
ROWS = {
    #          beginning   contrib  income   distributions
    "ashford": (119_200, 5_000, 25_000, 12_000),
    "shah": (2_264_800, 95_000, 475_000, 228_000),
    "psv": (2_086_000, 87_500, 406_250, 210_000),
    "ps2": (0, 0, 31_250, 0),
    "dumont": (1_490_000, 62_500, 312_500, 150_000),
}


def _moves(key: str, *, tax_exempt: bool) -> Movements:
    beginning, contrib, income, dist = ROWS[key]
    return Movements(
        beginning=D(beginning),
        contributions_cash=D(contrib),
        income=D(income),
        other_increases=D(TAX_EXEMPT[key]) if tax_exempt else D(0),
        distributions_cash=D(dist),
    )


def _partners(*, fixed: bool) -> list[CapitalPartner]:
    return [
        CapitalPartner(
            key,
            {
                "tax": _moves(key, tax_exempt=fixed),
                "704b": _moves(key, tax_exempt=True),
                "book": _moves(key, tax_exempt=True),
            },
        )
        for key in ROWS
    ]


THROUGH = Movements(beginning=D(2_086_000), contributions_cash=D(87_500), income=D(146_335))
TRANSFER = Transfer(
    on=date(2025, 6, 30),
    transferor="psv",
    transferee="ps2",
    points=D(5),
    transferor_points=D(35),
    price=D(360_000),
    through={b: THROUGH for b in BASES},
)


def test_the_transfer_moves_331405_in_all_three_bases_and_nets_to_zero() -> None:
    found = capital(_partners(fixed=True), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    (moved,) = found.transfers
    assert moved.capital_at_date == {b: D(2_319_835) for b in BASES}
    assert moved.transferred == {b: D(331_405) for b in BASES}
    assert moved.section_743b_placeholder == D(28_595)
    for b in BASES:
        assert found.row("psv", b).columns["transfers"] == D(-331_405)
        assert found.row("ps2", b).columns["transfers"] == D(331_405)
        assert found.totals[b]["transfers"] == 0
    assert found.checks["transfers_net_zero"] and found.checks["crossfoot"]


def test_before_the_fix_the_tax_column_omits_6200_and_m2_is_off() -> None:
    found = capital(_partners(fixed=False), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    assert found.m2.lines["9"] == D(6_860_000)
    assert found.m2.off == D(-6_200) and not found.m2.ties
    assert found.checks["m2_ties"] is False
    assert found.totals["book"]["ending"] == L21  # the book column has it


def test_after_the_fix_m2_ties_and_its_lines_foot() -> None:
    found = capital(_partners(fixed=True), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    lines = found.m2.lines
    assert lines["1"] == D(5_960_000)
    assert lines["2a"] == D(250_000) and lines["2b"] == 0
    assert lines["3"] == D(1_250_000) and lines["4"] == D(6_200)
    assert lines["5"] == D(7_466_200)
    assert lines["6a"] == D(600_000) and lines["8"] == D(600_000)
    assert lines["9"] == L21 and found.m2.off == 0 and found.m2.ties
    assert [found.row(k, "tax").columns["other_increases"] for k in ROWS] == [
        D(124),
        D(2_356),
        D(2_015),
        D(155),
        D(1_550),
    ]
    assert sum(found.ending.values(), D(0)) == L21
    assert all(found.checks.values())


def test_each_row_crossfoots_and_the_endings_are_item_l() -> None:
    found = capital(_partners(fixed=True), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    for row in found.rows:
        c = row.columns
        assert c["ending"] == (
            c["beginning"]
            + c["contributions_cash"]
            + c["contributions_property"]
            + c["income"]
            + c["other_increases"]
            - c["distributions_cash"]
            - c["distributions_property"]
            - c["other_decreases"]
            + c["transfers"]
        )
    assert found.ending["ps2"] == D(31_250 + 155 + 331_405)
    assert found.book_704b_differs == ()  # no revaluation or §704(c) item


def test_a_704b_revaluation_is_named_for_the_reviewer() -> None:
    partners = _partners(fixed=True)
    shah = partners[1]
    revalued = replace(
        shah,
        bases={**shah.bases, "704b": replace(shah.bases["704b"], other_increases=D(9_000))},
    )
    found = capital([*partners[:1], revalued, *partners[2:]], m2_basis="tax")
    assert found.book_704b_differs == ("shah",)


def test_the_transferred_share_rounds_half_up_to_the_dollar() -> None:
    odd = Movements(beginning=D(10))
    partners = [
        CapitalPartner("a", {b: odd for b in BASES}),
        CapitalPartner("b", {b: Movements() for b in BASES}),
    ]
    half = replace(
        TRANSFER, transferor="a", transferee="b", points=D(1), transferor_points=D(4),
        through={b: odd for b in BASES},
    )  # fmt: skip
    found = capital(partners, [half])
    assert found.transfers[0].transferred["tax"] == D(3)  # 2.5 → 3
    assert found.row("a", "tax").columns["ending"] == D(7)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"transferee": "psv"}, "transfer_to_self"),
        ({"transferee": "ghost"}, "unknown_partner"),
        ({"points": D(36)}, "transfer_points_invalid"),
        ({"points": D(0)}, "transfer_points_invalid"),
        ({"transferor_points": D(0)}, "transfer_points_invalid"),
        ({"price": D("360000.50")}, "whole_dollars_only"),
        ({"through": {"tax": THROUGH}}, "every_basis_required"),
    ],
)
def test_a_bad_transfer_is_refused(change: dict[str, object], code: str) -> None:
    with pytest.raises(CapitalInvalid) as refused:
        capital(_partners(fixed=True), [replace(TRANSFER, **change)])
    assert refused.value.code == code


def test_partners_must_be_unique_whole_dollar_and_in_every_basis() -> None:
    with pytest.raises(CapitalInvalid, match="partners_required"):
        capital([])
    one = _partners(fixed=True)[0]
    with pytest.raises(CapitalInvalid, match="partners_required"):
        capital([one, one])
    with pytest.raises(CapitalInvalid, match="every_basis_required"):
        capital([replace(one, bases={"tax": one.bases["tax"]})])
    cents = replace(one, bases={b: Movements(beginning=D("0.5")) for b in BASES})
    with pytest.raises(CapitalInvalid, match="whole_dollars_only"):
        capital([cents])


def test_the_stamp_is_stable_and_moves_with_the_inputs() -> None:
    a = capital(_partners(fixed=True), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    b = capital(_partners(fixed=True), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    c = capital(_partners(fixed=False), [TRANSFER], m2_basis="tax", schedule_l_line_21=L21)
    assert a.stamp == b.stamp and a.stamp.engine_name == "entity.capital"
    assert a.stamp.inputs_hash != c.stamp.inputs_hash
