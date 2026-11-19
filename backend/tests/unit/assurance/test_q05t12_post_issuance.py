"""Q-05-T12 (TASK-8718; SPEC-711 AC-15 to AC-18; DEC-5714): PI-01 computes 1,163,480 to 1,151,230
and 16,861,000 to 16,848,750, (12,250) below clearly trivial 12,610 at 4.9% of 252,200; "No action"
is recommended only below clearly trivial with no disclosure affected; every option is reserved to
the engagement partner, and the agent's capability names no decide action."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.assurance.compute.post_issuance import LineIn, compare, evaluate, options

D = Decimal


def test_ac_pi01_comparison_and_evaluation() -> None:
    lines = compare(
        [
            LineIn("net_assets", "Net assets available for benefits", D("1163480"), D("1151230")),
            LineIn("total_assets", "Total assets", D("16861000"), D("16848750")),
        ]
    )
    assert [ln.difference for ln in lines] == [D("-12250"), D("-12250")]
    ev = evaluate(D("-12250"), clearly_trivial=D("12610"), overall_materiality=D("252200"))
    assert ev.below_clearly_trivial
    assert ev.share_pct == D("4.9")


def test_ac_no_action_is_recommended_only_when_code_marks_it_eligible() -> None:
    below = evaluate(D("-12250"), clearly_trivial=D("12610"), overall_materiality=D("252200"))
    above = evaluate(D("-15000"), clearly_trivial=D("12610"), overall_materiality=D("252200"))
    assert options(below, disclosure_affected=False).recommended == "no_action"
    assert options(below, disclosure_affected=True).recommended is None
    assert options(above, disclosure_affected=False).recommended is None
    assert options(below, disclosure_affected=False).reserved_to == "engagement_partner"
