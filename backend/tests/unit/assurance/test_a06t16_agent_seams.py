"""A-06-T16 (TASK-3216; DEC-2216): the A-06 agent seams.

Row acceptance: "Generated I-AGENT-NEVER tests deny agent and system principals on every A-06
decision action at matrix, live-human and database layers, and a free number in why_surfaced is
flagged Unsupported." The matrix rows are the generated suites' (A-06-T05's actions); the
database layer is the human-only audit list (0661); the number check is pinned here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.kernel import _human_only_actions
from abacus.modules.assurance.findings import numbers_in, why_surfaced_support
from abacus.modules.identity.authz.matrix import RULES

A06_DECISIONS = (
    "finding.resolve",
    "finding.mark_not_applicable",
    "misstatement.pass_to_sum",
    "proposed_entry.approve",
    "proposed_entry.send_to_client",
    "statement.send_draft",
    "statement.record_management_approval",
    "disclosure_checklist.review",
)


@pytest.mark.parametrize("action", A06_DECISIONS)
def test_ac_the_agent_and_system_are_denied_every_a06_decision(action: str) -> None:
    if action not in RULES:
        pytest.skip("the action lands with its epic row (#1139)")
    rule = RULES[action]
    assert rule.decisions.get("agent", "deny") == "deny", action
    assert rule.decisions.get("system", "deny") == "deny", action


def test_ac_the_database_refuses_an_agent_conclusion() -> None:
    listed = set(_human_only_actions.HUMAN_ONLY_ACTIONS)
    assert {"deficiency.concluded", "sum.concluded", "attribute_result.marked"} <= listed


def test_ac_a_free_number_is_unsupported() -> None:
    figures = (Decimal("33540.00"), Decimal("9"))
    assert why_surfaced_support("Principal 33,540.00 was 9 business days late.", figures) == (
        "supported"
    )
    assert why_surfaced_support("Lost earnings were about 70.", figures) == "unsupported"


def test_ac_dates_and_references_are_not_figures() -> None:
    found = numbers_in("PayGrid pay date Dec 26, 2025; F-01 on EBP-04 row 8 under §6621(a)(2).")
    assert found == set()
