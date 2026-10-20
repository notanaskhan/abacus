"""SPEC-300 (TASK-301): materiality computed by code and decided by the partner; risks combined
by code and approved by the partner."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.fieldwork.planning import (
    PlanningInvalid,
    RiskIn,
    clean_risk,
    compute,
    rmm,
)
from abacus.modules.identity.authz.matrix import RULES


def test_ac1_amounts_are_computed_from_the_basis() -> None:
    found = compute(Decimal("16812400"), Decimal("1.5"), Decimal("75"), Decimal("5"))
    assert found.overall == Decimal("252200")  # 252,186 to the nearest hundred
    assert found.performance == Decimal("189200")  # 189,150
    assert found.trivial == Decimal("12600")  # 12,610


def test_ac1_small_amounts_round_to_the_dollar_never_zero() -> None:
    found = compute(Decimal("20000"), Decimal("2"), Decimal("50"), Decimal("1"))
    assert (found.overall, found.performance, found.trivial) == (
        Decimal("400"),
        Decimal("200"),
        Decimal("4"),
    )
    assert compute(Decimal("100"), Decimal("1"), Decimal("1"), Decimal("1")).trivial == 1


@pytest.mark.parametrize(
    ("basis", "rate", "pm", "ct"),
    [
        ("0", "1", "75", "5"),
        ("100", "0", "75", "5"),
        ("100", "1", "101", "5"),
        ("100", "1", "5", "6"),
    ],
)
def test_ac1_bad_bases_are_refused(basis: str, rate: str, pm: str, ct: str) -> None:
    with pytest.raises(PlanningInvalid):
        compute(Decimal(basis), Decimal(rate), Decimal(pm), Decimal(ct))


@pytest.mark.parametrize(
    ("inherent", "control", "expected"),
    [
        ("low", "low", "low"),
        ("low", "moderate", "low"),
        ("moderate", "moderate", "moderate"),
        ("low", "maximum", "moderate"),
        ("high", "low", "moderate"),
        ("moderate", "high", "high"),
        ("high", "maximum", "high"),
    ],
)
def test_ac4_rmm_combines_inherent_and_control(inherent: str, control: str, expected: str) -> None:
    assert rmm(inherent, control) == expected


def _risk(**over: object) -> RiskIn:
    base: dict[str, object] = {
        "title": " Revenue recognised early ",
        "area": "Revenue",
        "level": "assertion",
        "assertions": ["cut_off", "existence"],
        "inherent": "high",
        "control": "moderate",
        "significant": False,
        "fraud": "none",
        "rationale": None,
    }
    return RiskIn(**{**base, **over})  # type: ignore[arg-type]  # test overrides


def test_ac4_a_risk_is_trimmed_and_its_assertions_ordered() -> None:
    clean = clean_risk(_risk())
    assert clean.title == "Revenue recognised early"
    assert clean.assertions == ["existence", "cut_off"]


def test_ac5_a_significant_risk_or_rebuttal_needs_a_rationale() -> None:
    with pytest.raises(PlanningInvalid):
        clean_risk(_risk(significant=True))
    with pytest.raises(PlanningInvalid):
        clean_risk(_risk(fraud="rebuttal", rationale="  "))
    assert clean_risk(_risk(fraud="rebuttal", rationale="Simple revenue")).rationale


def test_ac4_unknown_values_are_refused() -> None:
    for over in ({"level": "x"}, {"inherent": "max"}, {"assertions": ["truth"]}, {"title": ""}):
        with pytest.raises(PlanningInvalid):
            clean_risk(_risk(**over))


def test_ac2_ac5_only_the_partner_decides_and_approves() -> None:
    for action in ("materiality.decide", "risk.approve"):
        decisions = RULES[action].decisions
        assert decisions.get("engagement_partner") == "allow"
        assert decisions.get("agent") == "deny"
        assert "manager" not in decisions and "senior" not in decisions
    assert RULES["risk.assess"].decisions.get("senior") == "allow"
    assert RULES["risk.assess"].decisions.get("agent") == "deny"
