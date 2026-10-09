"""Retrievability tiers by rule (SPEC-022; TASK-038 D1). Pure code; rules never come from client
text, and descriptions are only matched against fixed keywords.

Precedence (Q2): a manual override, else the firm's own tier (methodology template or imported
list), else the first matching rule, else unclassified. An A item names the dataset it needs, so
the live connection's capabilities decide whether it can be retrieved (AC-3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

Tier = Literal["A", "B", "C", "D", "E"]
Source = Literal["override", "methodology", "rule"]
RETRIEVABLE: Final = frozenset({"A", "B", "C"})
# For audit references (integers only, never text).
TIER_INDEX: Final = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    tier: Tier
    dataset: str | None = None


def _words(*phrases: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(phrases) + r")\b", re.IGNORECASE)


# Ordered: the first match wins. Small and conservative on purpose (D1): a wrong tier costs more
# than a missing one. Each id is stable once released (it is audited).
RULES: Final[tuple[Rule, ...]] = (
    Rule("tb-1", _words(r"trial balances?", r"TB"), "A", "trial_balance"),
    Rule("gl-1", _words(r"general ledger", r"GL detail", r"GL listing"), "A", "general_ledger"),
    Rule("je-1", _words(r"journal (?:entries|entry|listing)s?"), "A", "journals"),
    Rule(
        "ar-1",
        _words(r"aged (?:receivables|debtors)", r"AR aging", r"receivables aging"),
        "A",
        "ar_aging",
    ),
    Rule(
        "ap-1",
        _words(r"aged (?:payables|creditors)", r"AP aging", r"payables aging"),
        "A",
        "ap_aging",
    ),
    Rule("bc-1", _words(r"bank confirmations?", r"confirmations? from (?:the )?bank"), "E"),
    Rule("lg-1", _words(r"legal letters?", r"attorney letters?", r"lawyers?'? letters?"), "E"),
    Rule("ct-1", _words(r"contracts?", r"agreements?", r"leases?"), "E"),
    Rule("bm-1", _words(r"board minutes", r"minutes of (?:the )?board"), "E"),
    Rule("iv-1", _words(r"invoices?", r"bills?"), "C"),
    Rule("rc-1", _words(r"reconciliations?", r"roll-?forwards?", r"schedules?"), "D"),
)
_BY_ID: Final = {rule.id: rule for rule in RULES}


@dataclass(frozen=True)
class Classification:
    tier: Tier | None
    dataset: str | None
    source: Source | None
    rule_id: str | None


def _rule_for(description: str, area: str) -> Rule | None:
    text = f"{description}\n{area}"
    return next((rule for rule in RULES if rule.pattern.search(text)), None)


def classify(
    description: str,
    area: str,
    *,
    firm_tier: str | None = None,
    override: str | None = None,
) -> Classification:
    """The item's tier, dataset (A only) and where the tier came from (AC-1)."""
    rule = _rule_for(description, area)
    tier: str | None
    source: Source | None
    if override is not None:
        tier, source = override, "override"
    elif firm_tier is not None:
        tier, source = firm_tier, "methodology"
    elif rule is not None:
        tier, source = rule.tier, "rule"
    else:
        return Classification(None, None, None, None)
    dataset = rule.dataset if tier == "A" and rule is not None and rule.tier == "A" else None
    return Classification(_tier(tier), dataset, source, rule.id if rule is not None else None)


def _tier(value: str) -> Tier:
    if value not in ("A", "B", "C", "D", "E"):
        raise ValueError(f"not a tier: {value!r}")
    return value


def rule(rule_id: str) -> Rule | None:
    return _BY_ID.get(rule_id)
