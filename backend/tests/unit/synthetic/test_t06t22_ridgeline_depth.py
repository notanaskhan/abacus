"""T-06-T22 (DEC-5635): the Ridgeline depth slice reproduces every TXP-03/08/09 tally and the
DF-34 badge 11, 10, 9."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus_tools.synthetic.scenarios.brightwater_hale import ridgeline_depth_slice as s

D = Decimal


def test_txp03_register_foots_and_ties() -> None:
    t = s.register_totals()
    assert t["cost"] == D("15752000")
    assert t["prior"] == D("1891667")
    assert t["current"] == D("733500")
    assert t["accumulated"] == D("2625167")
    assert s.depreciation_by_property() == {
        "Elm Street, Chicago": D("169500"),
        "Larimer Lofts, Denver": D("360000"),
        "Bergen Street, Brooklyn": D("204000"),
    }
    assert sum(s.LAND.values()) == D("3600000")


def test_txp03_larimer_check_ties_on_the_feb_3_contract_and_the_roof_is_not_qip() -> None:
    assert s.bonus_check(None) == "check"
    assert s.bonus_check(s.LARIMER_BINDING_CONTRACT) == "tie"
    assert s.bonus_check(date(2025, 1, 10)) == "check"
    assert all("QIP" not in a.life for a in s.REGISTER)


def test_txp08_four_of_five_reconcile_and_pell_ii_is_off_28_595() -> None:
    off = {b.partner: b.off for b in s.BASIS if b.off}
    assert next(b for b in s.BASIS if b.partner == "Pell Street II LLC").inside_share == D(
        "885225"
    )
    assert off == {"Pell Street II LLC": D("28595")}
    assert D("28595") == s.PELL_II_PRICE - s.PELL_II_ACQUIRED_SHARE
    assert sum((b.tax_capital for b in s.BASIS), D("0")) == D("6866200")
    assert sum((b.share_752 for b in s.BASIS), D("0")) == D("11048300")
    assert sum((b.outside for b in s.BASIS), D("0")) == D("17943095")
    assert sum((b.inside_share for b in s.BASIS), D("0")) == D("17914500")
    assert next(b for b in s.BASIS if b.partner == "Jonah Feld").outside == D("4676125")


def test_txp09_apportionment_ptet_and_credits() -> None:
    assert sum(st.numerator for st in s.STATES) == D("1231600")
    assert s.apportionment() == {"IL": D("46.0"), "CO": D("31.5"), "NY": D("22.5")}
    p = s.ptet()
    assert p == {"IL": D("28044"), "CO": D("17070"), "NY": D("18982")}
    assert sum(p.values()) == D("64096")
    for i, state in enumerate(("IL", "CO", "NY")):
        assert sum(c[i] for c in s.PTET_CREDITS.values()) == p[state]
    assert sum(s.PTET_CREDITS["Jonah Feld"]) == D("16025")
    assert all(st.paid == date(2026, 3, 12) for st in s.STATES)
    assert sum(1 for st in s.ny_gap_variant() if st.paid is not None) == 2


def test_df34_badge_reads_11_then_10_then_9() -> None:
    kinds = [k for _, k in s.ISSUES]
    assert (kinds.count("waiting_on_client"), kinds.count("review_point")) == (5, 6)
    assert [s.badge_after(n) for n in range(3)] == [11, 10, 9]
