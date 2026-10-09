"""SPEC-022 AC-1, AC-2 (TASK-038): tiers by precedence, and datasets for tier A only."""

from __future__ import annotations

import pytest

from abacus.modules.requests.classification import RULES, classify


@pytest.mark.parametrize(
    ("description", "tier", "dataset", "rule"),
    [
        ("Trial balance at year end", "A", "trial_balance", "tb-1"),
        ("Year-end TB", "A", "trial_balance", "tb-1"),
        ("General ledger detail for revenue", "A", "general_ledger", "gl-1"),
        ("Aged receivables listing", "A", "ar_aging", "ar-1"),
        ("Bank confirmation for all accounts", "E", None, "bc-1"),
        ("Sample of sales invoices", "C", None, "iv-1"),
        ("Fixed asset roll-forward", "D", None, "rc-1"),
    ],
)
def test_ac1_rules_classify_by_keyword(
    description: str, tier: str, dataset: str | None, rule: str
) -> None:
    found = classify(description, "Any area")
    assert (found.tier, found.dataset, found.source, found.rule_id) == (
        tier,
        dataset,
        "rule",
        rule,
    )


def test_ac1_anything_else_stays_unclassified() -> None:
    found = classify("Management representation letter", "Completion")
    assert (found.tier, found.dataset, found.source, found.rule_id) == (None, None, None, None)


def test_ac1_the_firm_tier_beats_the_rules_and_keeps_an_a_dataset() -> None:
    assert classify("Bank confirmation", "Cash", firm_tier="D").tier == "D"
    found = classify("Trial balance", "GL", firm_tier="A")
    assert (found.tier, found.dataset, found.source) == ("A", "trial_balance", "methodology")
    # A firm tier other than A never carries a dataset, even when a rule would.
    assert classify("Trial balance", "GL", firm_tier="D").dataset is None


def test_ac2_an_override_beats_everything() -> None:
    found = classify("Trial balance", "GL", firm_tier="A", override="E")
    assert (found.tier, found.dataset, found.source) == ("E", None, "override")


def test_ac1_rule_ids_are_unique_and_a_rules_name_a_dataset() -> None:
    assert len({r.id for r in RULES}) == len(RULES)
    assert all((r.dataset is not None) == (r.tier == "A") for r in RULES)


def test_ac1_rules_never_match_inside_words() -> None:
    # "TB" must be a word; "billing" isn't "bills".
    assert classify("Stub period analysis", "X").rule_id is None
    assert classify("Billing system walkthrough", "X").rule_id is None
