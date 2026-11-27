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


def test_t06t52_frames_foot_and_name_no_partnership_vocabulary() -> None:
    """T-06-T52 (DEC-6036): the exported frames foot (the slice raises otherwise) and carry no
    partnership words ("capital account", "partner", "K-1") on a corporation or a 990."""
    import json

    from abacus_tools.synthetic.scenarios.brightwater_hale.other_entities_slice import (
        txp13_frames,
    )

    frames = txp13_frames()
    a, b, c = frames["a"], frames["b"], frames["c"]
    assert isinstance(a, dict) and isinstance(b, dict) and isinstance(c, dict)
    assert a["aaa"] == "1488200"
    assert b["taxable_income"] == "7490000" and b["total"] == "2257200"
    assert c["total"] == "4014000" and c["fiscal_year_end"] == "2026-06-30"
    text = json.dumps(frames).lower()
    for word in ("capital account", "partner", "k-1"):
        assert word not in text, word
