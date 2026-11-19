"""T-06-T28 (TASK-8723; DEC-5717): the other-entity slice reproduces TXP-13 a and b by the engines:
Bluestem's AAA 1,240,000 + 860,000 + 12,400 - 4,200 - 620,000 = 1,488,200 with distributions
within AAA, the 70/30 shareholder rows, and Ashford's 2,257,200."""

from __future__ import annotations

from decimal import Decimal

from abacus_tools.synthetic.scenarios.brightwater_hale import other_entities_slice as s


def test_ac_bluestem_aaa_ends_at_1_488_200_with_distributions_within_aaa() -> None:
    roll = s.bluestem_aaa()
    assert roll.ending == Decimal("1488200")
    assert roll.distributions == s.DISTRIBUTIONS <= roll.before_distributions


def test_ac_the_shareholder_rows_are_the_engine_split() -> None:
    for column in range(4):
        total = sum((row[column] for row in s.ALLOCATION_ROWS.values()), Decimal(0))
        split = s.bluestem_split(total)
        assert {k: v[column] for k, v in s.ALLOCATION_ROWS.items()} == split


def test_ac_ashford_provision() -> None:
    assert s.ashford_provision() == Decimal("2257200")
