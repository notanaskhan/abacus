"""T-08-T11 (TASK-8726; DEC-5720): lines flag when the delta meets the threshold (percent and
amount), a zero prior has no percent, and an acceptance goes stale when a current value changes."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.compute.two_year import Threshold, compare, stale, values_hash

D = Decimal
MAP = [("1", "Wages"), ("2b", "Taxable interest"), ("34", "Overpaid"), ("8", "Other income")]
T = Threshold(D("10"), D("1000"), "variance-policy-v3")


def test_ac_flags_by_threshold_and_skips_small_moves() -> None:
    lines = compare(
        {"1": D("215000"), "2b": D("1800"), "34": D("2400"), "8": D("5000")},
        {"1": D("180000"), "2b": D("1500"), "34": D("2100"), "8": D("0")},
        MAP,
        T,
    )
    by = {ln.code: ln for ln in lines}
    assert by["1"].flagged and by["1"].delta_pct == D("19.4")
    assert not by["2b"].flagged and not by["34"].flagged
    assert by["8"].delta_pct is None and by["8"].flagged


def test_ac_an_acceptance_goes_stale_when_a_value_changes() -> None:
    first = compare({"1": D("215000")}, {"1": D("180000")}, MAP[:1], T)
    accepted = values_hash(first)
    assert not stale(accepted, first)
    changed = compare({"1": D("215100")}, {"1": D("180000")}, MAP[:1], T)
    assert stale(accepted, changed)
