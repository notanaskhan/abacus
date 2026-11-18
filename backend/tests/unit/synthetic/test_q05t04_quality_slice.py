"""The Q-05 quality and records slice foots every golden figure of Q-05 §5.3 (Q-05-T04; SPEC-711
AC-34; DEC-5613). Figures are computed from counts in the slice, so a changed count fails here."""

from __future__ import annotations

from decimal import Decimal

from abacus_tools.synthetic.scenarios.brightwater_hale import quality_slice as q

D = Decimal


def test_override_rate_is_206_of_3410_or_6_0_percent() -> None:
    o = q.overrides()
    assert [r.outputs for r in o.rows] == [412, 318, 880, 1260, 540]
    assert [r.overrides for r in o.rows] == [37, 29, 61, 63, 16]
    assert (o.outputs, o.overrides, o.rate) == (3410, 206, D("6.0"))


def test_denver_is_61_of_1128_or_5_4_percent() -> None:
    o = q.overrides(denver=True)
    assert [r.outputs for r in o.rows] == [96, 74, 290, 418, 250]
    assert (o.outputs, o.overrides, o.rate) == (1128, 61, D("5.4"))


def test_two_agents_above_tolerance_are_the_monitoring_findings() -> None:
    above = [r for r in q.overrides().rows if r.above_tolerance]
    assert [(r.label, r.rate, r.finding_ref) for r in above] == [
        ("EBP Audit Workpapers", D("9.0"), "QM-F-04"),
        ("K-1 Reconciliation Workpaper", D("9.1"), "QM-F-05"),
    ]
    assert sum(n for _, n in q.EBP_REASONS) == 37


def test_accuracy_is_1_minus_1320_over_41260() -> None:
    a = q.accuracy()
    assert (a.returns_filed, a.fields, a.changed, a.accuracy) == (145, 41260, 1320, D("96.8"))


def test_e0_tiles() -> None:
    t = q.tiles()
    assert (t.objectives_at_risk, t.objectives, t.findings_open) == (2, 24, 5)
    assert (t.consultations_open, t.days_to_evaluation) == (2, 92)
    assert q.register() == (24, 38, 58)


def test_pi01_is_below_clearly_trivial_at_4_9_percent() -> None:
    case = q.pi01()
    assert [line.difference for line in case.comparison] == [D("-12250")] * 3
    assert case.evaluation is not None
    assert case.evaluation.share_pct == D("4.9")
    assert case.evaluation.below_clearly_trivial


def test_batch_2026_q3_destroys_1201_in_the_fil02e_variant() -> None:
    canonical = q.batch_2026_q3()
    variant = q.batch_2026_q3(fil02e=True)
    assert (canonical.eligible_count, canonical.client_count) == (1204, 31)
    assert q.to_destroy(canonical) == 1204
    assert q.to_destroy(variant) == 1201
    assert canonical.confirmation_phrase == "DESTROY 2026-Q3"
