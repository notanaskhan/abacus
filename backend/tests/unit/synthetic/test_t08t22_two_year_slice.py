"""T-08-T22 (TASK-8936; DEC-5938): the Feld two-year slice foots to TAX-10's handoff by code: AGI
598,030 (+8.4%), total tax 123,223 (+11.2%), refund 253 (2024: 1,174), 8 lines over the firm
threshold (> $1,000 and > 10%), 7 of 8 accepted in a, 8 of 8 in c, 0 of 8 in d; the refund's
(78.4%) change is below $1,000 and not flagged; every line has its live map's code, group and
reference; x1 offers no Explain and names why."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.api import two_year_lines
from abacus_tools.synthetic.scenarios.brightwater_hale.two_year_slice import feld_two_year


def test_a_foots() -> None:
    a = feld_two_year("a")
    assert (a.agi, a.agi_delta_pct) == (Decimal("598030"), Decimal("8.4"))
    assert (a.total_tax, a.total_tax_delta_pct) == (Decimal("123223"), Decimal("11.2"))
    assert (a.refund, a.prior_refund) == (Decimal("253"), Decimal("1174"))
    assert (a.over_threshold, a.accepted) == (8, 7)
    refund = next(ln for ln in a.lines if ln.line_key == "1040.34")
    assert (refund.flagged, refund.below_reason, refund.total) == (False, "below_amount", "grand")
    assert [ln.line_key for ln in a.lines] == [c for c, _ in two_year_lines.LINE_MAPS["1040"]]
    assert all(ln.group is not None and ln.line_ref is not None for ln in a.lines)


def test_states() -> None:
    assert feld_two_year("c").accepted == 8
    assert feld_two_year("d").accepted == 0
    assert len(feld_two_year("b").lines) == 8
    assert feld_two_year("e").explaining
    x1 = feld_two_year("x1")
    assert not x1.explain_available
    assert x1.explain_unavailable_reason == "agents_off_for_taxpayer"


def test_only_the_proposed_line_offers_accept() -> None:
    a = feld_two_year("a")
    offered = [ln.line_key for ln in a.lines if "two_year.accept" in ln.allowed_actions]
    assert offered == ["scha.11"]
