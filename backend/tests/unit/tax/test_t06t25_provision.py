"""T-06-T25 (TASK-8720; E11; DEC-77): Ashford's provision 2,134,650 + 122,550 = 2,257,200 at an
ETR of 28.9%, and the B2 variant that does not tie reports its 1,200 as an unclassified
difference (never plugged)."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.compute.provision import blended_state_rate, provision, reconcile

D = Decimal
# Synthetic pretax income for the reconciliation (the handoff gives the totals and the ETR only).
PRETAX = D("7810000")


def test_ac_ashford_provision_and_etr() -> None:
    assert provision(D("2134650"), D("122550")) == D("2257200")
    rec = reconcile(
        PRETAX, current=D("2134650"), deferred=D("122550"), federal_rate=D("0.21"),
        state_rate=D("0.095"), items={},
    )  # fmt: skip
    assert rec.etr_pct == D("28.9")


def test_ac_the_b2_variant_reports_1200_unclassified() -> None:
    base = reconcile(
        PRETAX, current=D("2134650"), deferred=D("122550"), federal_rate=D("0.21"),
        state_rate=D("0.095"), items={},
    )  # fmt: skip
    tied = reconcile(
        PRETAX, current=D("2134650"), deferred=D("122550"), federal_rate=D("0.21"),
        state_rate=D("0.095"), items={"permanent": base.unclassified},
    )  # fmt: skip
    assert tied.ties
    off = reconcile(
        PRETAX, current=D("2134650"), deferred=D("122550"), federal_rate=D("0.21"),
        state_rate=D("0.095"), items={"permanent": base.unclassified - D("1200")},
    )  # fmt: skip
    assert off.unclassified == D("1200") and not off.ties
    assert blended_state_rate(D("0.095"), D("0.21")) == D("0.07505")
