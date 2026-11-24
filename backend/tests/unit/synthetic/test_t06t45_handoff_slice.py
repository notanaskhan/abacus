"""T-06-T45 (TASK-8935; DEC-5937): AUD-38's previews and TXP-13 d's landing from the slice foot:
121 + 5 + 2 = 128 accounts in the O4 table, 3,100,000 - 750,000 = 2,350,000, PP&E 6,050,000 +
1,380,000 - 1,050,000 = 6,380,000, the passed AJE-3 carried as a (68,400) candidate, and the
landing's counts map the record's prior-year / suggested / blank."""

from __future__ import annotations

from decimal import Decimal

from abacus_tools.synthetic.scenarios.brightwater_hale import tb_handoff_slice as s


def test_preview_footings() -> None:
    p = s.granite_peak_preview(chosen=True)
    assert p.counts.mapped + p.counts.suggested + p.counts.review == p.counts.total == 128
    assert p.book_income.pretax - p.book_income.income_tax_expense == p.book_income.net_income
    sources = [a.source for a in p.accounts]
    assert (sources.count("firm_mapping"), sources.count("tb_mapper"), sources.count("blank")) == (
        121,
        5,
        2,
    )
    assert "= 6,380,000" in p.schedule_rows[0].detail
    assert p.source is not None and p.source.balanced
    assert p.target is not None and len(p.target.team) == 3


def test_states() -> None:
    assert s.granite_peak_preview(chosen=False).status == "needs_review"
    assert s.granite_peak_not_available().gate == "not_released"
    assert s.granite_peak_superseded().gate == "superseded"


def test_landing() -> None:
    land = s.granite_peak_landing()
    assert land.counts is not None and land.counts.total == 128
    assert [(c.ref, c.amount) for c in land.candidates] == [("AJE-3", Decimal("-68400.00"))]
    rows = s.aud38_rows()
    assert set(rows) >= {"preview_ready", "preview_needs_review", "landing", "target"}
