# ac-test-author: ayushkbhatia
"""K-03-T18 (TASK-9011; K-03 §3.3; SHT-03 a, b, d, e; DEC-6017): the scoping goldens, by code.

Row acceptance: "Goldens give Harlow & Pike 'Shows 3 steps · 2 sheets · hides 1 · adds 6
requests', Granite Peak 'Shows 1 step · hides 0', rules 2 and 7 answer 422 naming both rules, and
no model is called." The 422 is the route's (the integration test); here the conflict the route
names is code's, and the evaluator imports nothing that reaches a model."""

from __future__ import annotations

import ast
import inspect

import pytest

from abacus.modules.methodology import scoping as engine
from abacus.modules.methodology.scoping import Condition, Rule, Shape

GROUP = "engagement.profile.group_audit"
FIRST_YEAR = "engagement.profile.first_year"
PERFORMED = "group_scoping.components.performed_by"
INVENTORY = "risk_register.inventory.significant"


def _rule(n: int, conditions: tuple[Condition, ...], effect: str, kind: str, ref: str) -> Rule:
    return Rule(f"r{n}", n, "and", conditions, effect, kind, ref)  # type: ignore[arg-type] -- the literals are checked by the engine


GROUP_YES = Condition(GROUP, "is", "yes")
FS_V6 = (
    _rule(1, (GROUP_YES,), "show", "step", "BH-FS-700"),
    _rule(2, (GROUP_YES,), "show", "step", "BH-FS-720"),
    _rule(3, (GROUP_YES, Condition(PERFORMED, "includes", "component_auditor")), "show", "step",
          "BH-FS-710"),
    _rule(4, (GROUP_YES,), "show", "request_group", "group_requests"),
    _rule(5, (GROUP_YES,), "hide", "section", "materiality_form.single_entity_benchmark"),
    _rule(6, (Condition(INVENTORY, "is", "yes"),), "show", "step", "BH-FS-345"),
)  # fmt: skip
SHAPE = Shape(
    {"BH-FS-700": frozenset({"group_scoping"}), "BH-FS-710": frozenset({"component_tracker"})},
    {"group_requests": 6},
)
HARLOW = {GROUP: "yes", PERFORMED: frozenset({"group_team", "component_auditor"})}
GRANITE = {GROUP: "no", PERFORMED: None, INVENTORY: "yes"}


def test_k03t18_harlow_and_pike_previews_three_steps_two_sheets_one_hide_six_requests() -> None:
    found = engine.evaluate_scoping_rules(FS_V6, HARLOW, SHAPE)
    assert found.summary == "Shows 3 steps · 2 sheets · hides 1 · adds 6 requests"
    assert [r for _, r in found.results] == [
        "shows",
        "shows",
        "shows",
        "shows",
        "hides",
        "no_answer",
    ]  # fmt: skip  (rule 6: Harlow & Pike has not answered the inventory question)


def test_k03t18_granite_peak_previews_one_step_and_no_hide() -> None:
    found = engine.evaluate_scoping_rules(FS_V6, GRANITE, SHAPE)
    assert found.summary == "Shows 1 step · hides 0"
    assert [r for _, r in found.results] == ["no_change"] * 5 + ["shows"]


def test_k03t18_the_assertion_level_rule_has_no_answer_yet_on_harlow_and_pike() -> None:
    rule7 = Rule(
        "r7", 7, "and",
        (Condition("risk_register.inventory.assertion", "is", "valuation"),
         Condition("risk_register.inventory.rmm", "is", "high")),
        "show", "row", "BH-FS-345.4",
    )  # fmt: skip
    assert engine.evaluate_rule(rule7, HARLOW) == "no_answer"
    answered = {"risk_register.inventory.assertion": frozenset({"valuation", "existence"}),
                "risk_register.inventory.rmm": "high"}  # fmt: skip
    assert engine.evaluate_rule(rule7, answered) == "shows"
    assert engine.evaluate_rule(rule7, answered | {"risk_register.inventory.rmm": "low"}) == (
        "no_change"
    )


def test_k03t18_rules_2_and_7_conflict_on_bh_fs_720() -> None:
    rule7 = _rule(7, (Condition(FIRST_YEAR, "is", "yes"),), "hide", "step", "BH-FS-720")
    assert engine.conflicts(FS_V6) == []
    assert engine.conflicts((*FS_V6, rule7)) == [engine.Conflict(2, 7, "step", "BH-FS-720")]


@pytest.mark.parametrize(
    ("operator", "value", "answer", "expected"),
    [
        ("is", "yes", "Yes", True),
        ("is_not", "yes", "no", True),
        ("includes", "component_auditor", frozenset({"group_team"}), False),
        ("is_answered", None, None, False),
        ("is_empty", None, None, True),
        ("is", "yes", None, None),
        ("is", "yes", "  ", None),
    ],
)
def test_k03t18_the_five_operators(
    operator: engine.Operator, value: str | None, answer: engine.Answer, expected: bool | None
) -> None:
    assert engine.condition_holds(Condition("s", operator, value), {"s": answer}) is expected


def test_k03t18_an_or_group_applies_on_any_true_condition() -> None:
    either = Rule("o", 1, "or", (Condition("a", "is", "yes"), Condition("b", "is", "yes")),
                  "show", "sheet", "s")  # fmt: skip
    assert engine.evaluate_rule(either, {"a": "no", "b": "yes"}) == "shows"
    assert engine.evaluate_rule(either, {"a": "no"}) == "no_answer"
    assert engine.evaluate_rule(either, {"a": "no", "b": "no"}) == "no_change"


def test_k03t18_the_evaluator_reaches_no_model() -> None:
    """Code evaluates every rule (ADR-050): the engine imports nothing but the standard library."""
    tree = ast.parse(inspect.getsource(engine))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in n.names
    }
    assert not {m for m in imported if m.startswith("abacus")}
