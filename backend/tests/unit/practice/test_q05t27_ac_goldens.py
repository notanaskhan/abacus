# ac-test-author: notanaskhan
"""Q-05-T27 (TASK-8942; SPEC-711 AC-1 to AC-4; ADR-078): golden figures for the quality dashboard
and the exact-decimal tolerance edge, typed from the ADM-11 handoff, never imported from it.

- The seed's five agents read exactly the handoff's outputs and overrides, firm-wide and Denver's,
  footing 3,410 outputs and 206 overrides (6.0%); a one-output or one-row drift fails.
- The tolerance comparison is exact: 199 of 2,500 (7.96%) and 201 of 2,500 (8.04%) both read 8.0%
  and are not above the 8% tolerance; 202 of 2,500 (8.08%) reads 8.1% and is above it.
- Accuracy 1 - 1,320 / 41,260 = 96.8% over 145 returns; the register imports 24 / 38 / 58.
"""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.practice.compute import override_rates as rates
from abacus_tools.synthetic.scenarios.brightwater_hale import quality_slice as q

FIRM = {
    "ebp_audit_workpapers": (412, 37, Decimal("9.0")),
    "k1_reconciliation_workpaper": (318, 29, Decimal("9.1")),
    "missing_document_chaser": (880, 61, Decimal("6.9")),
    "return_review_packet": (1260, 63, Decimal("5.0")),
    "bank_reconciliation": (540, 16, Decimal("3.0")),
}
DENVER = {
    "ebp_audit_workpapers": (96, 8),
    "k1_reconciliation_workpaper": (74, 6),
    "missing_document_chaser": (290, 19),
    "return_review_packet": (418, 21),
    "bank_reconciliation": (250, 7),
}


def test_ac3_seed_agents_are_the_handoffs_exactly() -> None:
    rows = {r.agent_key: (r.outputs, r.overrides, r.rate) for r in q.agent_rows()}
    assert rows == FIRM
    above = sorted(r.agent_key for r in q.agent_rows() if r.above_tolerance)
    assert above == ["ebp_audit_workpapers", "k1_reconciliation_workpaper"]


def test_ac3_denver_subset_is_the_handoffs_exactly() -> None:
    rows = {r.agent_key: (r.outputs, r.overrides) for r in q.agent_rows(denver=True)}
    assert rows == DENVER


def test_ac3_firm_totals_foot_3410_and_206() -> None:
    o = q.overrides()
    assert (o.outputs, o.overrides, o.rate) == (3410, 206, Decimal("6.0"))


def test_ac3_the_tolerance_edge_is_exact() -> None:
    def outcome(n: int, k: int) -> list[rates.OutcomeRow]:
        return [rates.OutcomeRow("a", "changed")] * k + [rates.OutcomeRow("a", "adopted")] * (
            n - k
        )

    for k, shown, above in ((199, "8.0", False), (201, "8.0", False), (202, "8.1", True)):
        (row,) = rates.per_agent(outcome(2500, k), Decimal("8"))
        assert (row.rate, row.above_tolerance) == (Decimal(shown), above), k


def test_ac3_an_unrated_agent_is_never_above() -> None:
    few = [rates.OutcomeRow("a", "rejected")] * 20 + [rates.OutcomeRow("a", "adopted")] * 4
    (row,) = rates.per_agent(few, Decimal("8"))
    assert (row.rated, row.above_tolerance) == (False, False)


def test_ac4_accuracy_and_register() -> None:
    a = q.accuracy()
    assert (a.returns_filed, a.accuracy) == (145, Decimal("96.8"))
    assert q.register() == (24, 38, 58)
