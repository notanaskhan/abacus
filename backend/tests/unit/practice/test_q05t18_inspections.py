"""Q-05-T18 (TASK-8822; SPEC-711 AC-6 to AC-11): inspections, findings, annual evaluation.

Row acceptance: "Selecting Sterling Freight with Thomas Whitcombe answers 422
inspector_not_objective, the five findings foot to 3 + 2, and conclusion stays 409 until all six
inspections conclude." Here: the codes; the risk score is deterministic and orders by weight then
seed; the evaluation card is firm-scope with three code-fixed options.
"""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.practice import inspections as s


def test_ac_the_codes() -> None:
    assert s.NotObjective.code == "inspector_not_objective"
    assert s.InspectionsOpen.code == "inspections_open"


def test_the_risk_score_is_deterministic() -> None:
    weights: dict[str, object] = {"attest": 3, "archived": 1, "kind_assurance": 2}
    a = s.score(weights, {"attest": True, "archived": True, "kind_assurance": True}, 4242, "w1")
    b = s.score(weights, {"attest": True, "archived": True, "kind_assurance": True}, 4242, "w1")
    c = s.score(weights, {"attest": False, "archived": True}, 4242, "w2")
    assert a == b and a > c and Decimal(6) <= a < Decimal("6.01")


def test_the_evaluation_card_has_three_fixed_options() -> None:
    assert s.EVALUATION_KIND == "qm_annual_evaluation"
    assert [o["key"] for o in s.EVALUATION_OPTIONS] == [
        "reasonable_assurance",
        "except_for",
        "does_not",
    ]
