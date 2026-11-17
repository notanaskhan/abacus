"""C-01-T47 (TASK-8536; ADR-078): independent acceptance tests for C-01's closes services.

Written from SPEC-655 F5-F9 and the CLS-04/05/06/10 handoff figures, not from the services' own
tests: schedules tie, tie once posted and go off by the cent; staleness is a change of the inputs
hash; flux needs both legs; classify_entry always holds an attest client's entry; a reconciling
item's drafted entry balances; the close agent's tools only read, compute and propose.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from abacus.modules.closes import flux
from abacus.modules.closes.agent_tools import AGENT_TOOLS
from abacus.modules.closes.compute import schedules
from abacus.modules.closes.reconciliations import entry_lines
from abacus.modules.methodology.standards_contract import (
    AjeThresholdsPayload,
    PolicyRef,
    classify_entry,
)
from abacus.modules.workpapers import api as engine

MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"
D = Decimal

# ---- schedules (CLS-04): Cedar Mutual's $8,400 policy, $700 a month ---------------------------

CEDAR = schedules.Arrangement(
    kind="prepaid",
    scheduled_total=D("8400"),
    start_on=date(2026, 1, 1),
    finish_on=date(2026, 12, 31),
)


def test_the_prepaid_schedule_amortizes_700_a_month() -> None:
    assert schedules.balance_at(CEDAR, "2026-07") == D("3500.00")
    assert schedules.balance_at(CEDAR, "2026-08") == D("2800.00")
    assert schedules.balance_at(CEDAR, "2026-12") == D("0.00")


def test_gl_3500_ties_once_aje_02_posts_and_ties_when_recorded() -> None:
    pending = [schedules.PendingEntry("AJE-02", D("-700"))]
    result = schedules.tie(D("3500"), D("2800"), pending)
    assert (result.tie, result.pending_entry_number) == ("ties_once_posted", "AJE-02")
    assert schedules.tie(D("2800"), D("2800"), recorded=True).tie == "recorded"


def test_a_difference_no_pending_entry_explains_is_off_by_the_cent() -> None:
    result = schedules.tie(
        D("3560.00"), D("2800.00"), [schedules.PendingEntry("AJE-02", D("-700"))]
    )
    assert (result.tie, result.off_by) == ("off", D("760.00"))
    assert schedules.tie(D("2800.01"), D("2800.00")).tie == "off"


def test_staleness_is_a_change_of_the_inputs_hash() -> None:
    h = schedules.inputs_hash(CEDAR, "2026-08", D("3500"))
    assert h == schedules.inputs_hash(CEDAR, "2026-08", D("3500.00"))
    assert h != schedules.inputs_hash(CEDAR, "2026-08", D("2800"))
    assert h != schedules.inputs_hash(CEDAR, "2026-09", D("3500"))


# ---- flux (CLS-10): over needs both the percent and the amount --------------------------------

T = engine.Thresholds(flux.DEFAULT_PCT, flux.DEFAULT_AMOUNT)


def _lines(*rows: tuple[str, str | None, str]) -> dict[str, flux.Line]:
    src = [
        flux.Source(k, k, D(cur), None if prior is None else D(prior)) for k, prior, cur in rows
    ]
    return {line.key: line for line in flux.lines_of(src, T)}


def test_flux_needs_both_legs() -> None:
    by = _lines(
        ("repairs", "640", "3200"),  # +400%, +2,560: over both
        ("payroll", "61240", "68910"),  # +12.5%, +7,670: over both
        ("marketing", "3980", "2450"),  # -38.4% but 1,530 < 2,500: within
        ("rent", "9800", "9800"),
    )
    assert by["repairs"].test == by["payroll"].test == "over_both"
    assert by["marketing"].test == by["rent"].test == "within"
    assert by["payroll"].status == "unexplained"


def test_no_prior_is_not_comparable_never_an_invented_value() -> None:
    line = _lines(("new", None, "500"))["new"]
    assert (line.test, line.prior, line.change, line.pct) == ("not_comparable", None, None, None)


def test_flux_staleness_follows_the_inputs() -> None:
    a = [flux.Source("repairs", "Repairs", D("3200"), D("640"))]
    b = [flux.Source("repairs", "Repairs", D("3201"), D("640"))]
    assert flux.inputs_hash("mom", a, T) != flux.inputs_hash("mom", b, T)
    assert flux.inputs_hash("mom", a, T) != flux.inputs_hash("yoy", a, T)


# ---- classify_entry: attest entries always held ----------------------------------------------

POLICY = PolicyRef("bh-aje-thresholds", uuid.uuid4(), 2, "BH AJE thresholds")
RULES = AjeThresholdsPayload.model_validate(
    {
        "kind": "aje_thresholds",
        "rows": [
            {"account_class": "Prepaids", "rule": "limit", "limit_usd": 10_000,
             "approver_level": "senior_or_above", "batch": True},
            {"account_class": "All other classes", "rule": "review_required", "limit_usd": None,
             "approver_level": "manager_or_partner", "batch": False},
            {"account_class": "Attest clients", "rule": "always_held", "limit_usd": None,
             "approver_level": "partner", "batch": False},
        ],
    }
)  # fmt: skip


@pytest.mark.parametrize("amount", [1, 700, 10_000, 250_000])
def test_an_attest_clients_entry_is_always_held(amount: int) -> None:
    got = classify_entry(
        RULES, POLICY, account_class="Prepaids", amount_usd=amount, attest_client=True
    )
    assert (got.outcome, got.reason) == ("review_required", "attest_client")


def test_a_prepaid_entry_is_within_threshold_up_to_and_including_the_limit() -> None:
    at = classify_entry(
        RULES, POLICY, account_class="Prepaids", amount_usd=10_000, attest_client=False
    )
    over = classify_entry(
        RULES, POLICY, account_class="Prepaids", amount_usd=10_001, attest_client=False
    )
    unlisted = classify_entry(
        RULES, POLICY, account_class="Bank", amount_usd=380, attest_client=False
    )
    assert at.outcome == "within_threshold"
    assert (over.outcome, over.reason) == ("review_required", "over_limit")
    assert (unlisted.outcome, unlisted.reason) == ("review_required", "unlisted_class")


# ---- reconciliation drafts (CLS-05): the $380 refund ------------------------------------------


def test_an_unrecorded_deposit_drafts_dr_cash_cr_offset_and_balances() -> None:
    lines = entry_lines({"kind": "unrecorded_deposit", "amount": "380.00"}, "4410", "COGS-Dairy")
    assert lines == [("4410", D("380.00"), D(0)), ("COGS-Dairy", D(0), D("380.00"))]
    assert sum(d for _, d, _ in lines) == sum(c for _, _, c in lines)


def test_an_unrecorded_withdrawal_credits_cash() -> None:
    lines = entry_lines({"kind": "unrecorded_withdrawal", "amount": "-55.00"}, "4410", "Fees")
    assert lines == [("Fees", D("55.00"), D(0)), ("4410", D(0), D("55.00"))]


# ---- the close agent: read, compute and propose only ------------------------------------------


def test_the_close_agents_tools_only_read_compute_or_propose() -> None:
    kinds = {t.name: t.kind for t in AGENT_TOOLS}
    assert set(kinds.values()) <= {"read", "compute", "propose"}
    assert kinds["close.propose_aje"] == "propose"


def test_portal_principals_and_support_never_reach_a_close() -> None:
    doc = yaml.safe_load((MATRIX / "closes.yaml").read_text(encoding="utf-8"))
    for action, row in doc["actions"].items():
        for principal in ("client_contributor", "third_party", "platform_support"):
            if principal in row:
                assert row[principal] == "deny", (action, principal)
