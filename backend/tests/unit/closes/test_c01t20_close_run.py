"""C-01-T20 (TASK-8073; SPEC-655 F3, AC-28 to AC-31): the close run's code plan and executors.

Row acceptance: "Run 2 on the Copperleaf fixture plans 9 procedures in 5 groups (2 + 3 + 2 + 1 +
1), never runs more than 3 at once, holds the Square group on the decision card, and an agent
principal starting a run gets 403." The 403 is the route's (`_human_route`, the contract tests);
the 3 is P-10's `max_parallel_steps` for every engagement run.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.agents.engagement_run import MAX_PARALLEL
from abacus.modules.closes import procedures as p
from abacus.modules.closes.run_plan import (
    PendingTreatment,
    PlanRow,
    groups_of,
    plan_steps,
    select_rows,
    step_key,
)

CLOSE = uuid.UUID("00000000-0000-4000-8000-00000000c1a2")
ROWS = [
    PlanRow(
        uuid.uuid4(), n, account, name, procedure, "method", "quickbooks_online", "senior_signoff"
    )
    for n, (account, name, procedure) in enumerate(
        [
            ("4000", "Revenue", "recategorize"),
            ("6000", "Expenses", "recategorize"),
            ("1010", "Front Range Bank ••4410", "reconciliation"),
            ("1020", "Savings ••7731", "reconciliation"),
            ("2100", "Amex ••1009", "reconciliation"),
            ("1250", "Square clearing", "third_party_sales"),
            ("1260", "Shopify clearing", "third_party_sales"),
            ("1350", "Prepaid insurance", "amortization"),
            ("1500", "Roaster", "depreciation"),
        ]
    )
]


def test_ac_run_2_plans_9_procedures_in_5_groups() -> None:
    plan = plan_steps(ROWS, [], CLOSE)
    assert [n for _, n in groups_of(plan)] == [2, 3, 2, 1, 1]
    assert sum(n for _, n in groups_of(plan)) == 9
    assert MAX_PARALLEL == 3  # never more than 3 at once (the run's max_parallel_steps)
    assert all(s.arguments["close_id"] == str(CLOSE) for s in plan)


def test_ac_the_square_group_waits_on_the_treatment_card() -> None:
    pending = [PendingTreatment(uuid.uuid4(), "transfer 0828", Decimal("6412.40"), "1250")]
    plan = plan_steps(ROWS, pending, CLOSE)
    decisions = [s for s in plan if s.kind == "decision"]
    assert len(decisions) == 1 and decisions[0].arguments["decision_kind"] == "close_treatment"
    third = [s for s in plan if s.arguments.get("group") == "third_party" and s.kind == "compute"]
    assert third and all(s.depends_on == (decisions[0].key,) for s in third)
    others = [s for s in plan if s.kind == "compute" and s.arguments.get("group") != "third_party"]
    assert all(s.depends_on == () for s in others)  # the other groups run


@pytest.mark.parametrize(
    ("scope", "keys", "count"),
    [("all", (), 9), ("group", ("reconcile",), 3), ("accounts", ("1250", "1500"), 2)],
)
def test_scopes(scope: str, keys: tuple[str, ...], count: int) -> None:
    assert len(select_rows(ROWS, scope, keys)) == count


def test_failed_only_reruns_the_failed_rows() -> None:
    failed = frozenset({step_key(ROWS[6])})  # "Stopped at Shopify" (CLS-02 e)
    assert select_rows(ROWS, "failed_only", (), failed) == [ROWS[6]]


def test_reconcile_foots_the_figure_book() -> None:
    # ••4410: 184,236.18 + 6,412.40 - 5,658.08 = 184,990.50 = 184,610.50 + 380.00
    items = [
        p.OutstandingItem(
            "bank", "deposit_in_transit", "d1", Decimal("6412.40"), date(2026, 8, 31)
        ),
        p.OutstandingItem(
            "bank", "outstanding_check", "#2281", Decimal("-5658.08"), date(2026, 2, 19)
        ),
        p.OutstandingItem("book", "interest", "int", Decimal("380.00"), date(2026, 8, 31)),
    ]
    rec = p.reconcile_statement(
        Decimal("184236.18"), Decimal("184610.50"), items, date(2026, 8, 31)
    )
    assert (rec.adjusted_bank, rec.adjusted_book, rec.difference, rec.tally) == (
        Decimal("184990.50"),
        Decimal("184990.50"),
        Decimal("0.00"),
        "tie",
    )
    assert rec.stale_items == ("#2281",)  # 193 days at period end


def test_square_clearing_and_an_unmatched_transfer() -> None:
    payouts = [p.Payout("t1", Decimal("71482.36"), date(2026, 8, 31))]
    deposits = [p.Payout("d1", Decimal("71482.36"), date(2026, 9, 1))]
    ok = p.clear_third_party_sales(
        Decimal("73166.90"), Decimal("1684.54"), Decimal(0), payouts, deposits
    )
    assert (ok.expected_net, ok.difference, ok.tally) == (
        Decimal("71482.36"),
        Decimal("0.00"),
        "tie",
    )
    missing = p.clear_third_party_sales(
        Decimal("6412.40"),
        Decimal(0),
        Decimal(0),
        [p.Payout("x", Decimal("6412.40"), date(2026, 8, 28))],
        [],
    )
    assert missing.unmatched == ("x",) and missing.tally == "off"


def test_prepaid_8400_over_12_is_700_and_3500_vs_2800_is_off_by_700() -> None:
    s = p.amortize_prepaid(
        Decimal("8400"), 12, date(2026, 2, 1), date(2026, 8, 31), Decimal("2800.00")
    )
    assert s.monthly == Decimal("700.00") and s.months_elapsed == 7
    assert (s.ending_balance, s.off_by, s.tie) == (Decimal("3500.00"), Decimal("700.00"), "off")


def test_the_2500_capitalisation_test() -> None:
    d = p.depreciate_fixed_assets(
        [
            p.Addition("grinder", Decimal("2499.99"), 60, date(2026, 8, 1)),
            p.Addition("roaster", Decimal("36000.00"), 120, date(2026, 8, 1)),
        ],
        date(2026, 8, 31),
    )
    assert d.expensed == ("grinder",) and d.capitalised == ("roaster",)
    assert d.month_charge == Decimal("300.00")


def test_recategorize_first_rule_wins_and_accruals_roll() -> None:
    lines = [p.Line("r1", "6000", "Valley Equipment", "bearing", Decimal("2560.00"))]
    rules = [p.Rule("repairs", "valley equipment", "6100"), p.Rule("any", "bearing", "6900")]
    assert [x.to_account for x in p.recategorize(lines, rules)] == ["6100"]
    roll = p.roll_accruals(Decimal("1850.00"), Decimal("2140.00"))
    assert (roll.reversed_prior, roll.booked, roll.net_change) == (
        Decimal("-1850.00"),
        Decimal("2140.00"),
        Decimal("290.00"),
    )


def test_inputs_hash_is_stable() -> None:
    assert p.inputs_hash({"b": Decimal("1.00"), "a": [1]}) == p.inputs_hash(
        {"a": [1], "b": Decimal("1.00")}
    )
