"""ADR-078 catch-up lane, 2027 Q4 (Q-03-T171, TASK-3236): independent AC suites for the period's
amber rows that reached the end of S26 without one, written apart from the rows themselves.

Covered elsewhere already: A-04-T07/T18/T19 (A-04-T30), the A-05 services (A-05-T25, A-05-T29),
the adjustments (A-06-T17), the notices contract (N-04-T10) and C4 v1.1 (P-11-T20). Here:
A-04-T25 (internal control), A-06-T13 (the completion decision kinds), A-06-T19 (statements v1)
and T-03-T02/T04 (extensions, estimates and the payments engine). Each test holds a declaration
the plan states: who may act, what is human-only, what is insert-only, and how money rounds.
"""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.kernel.numeric import quantize_half_up
from abacus.modules.reporting import registry as reporting_registry

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
MOD = BACKEND / "src/abacus/modules"
CLIENTS = ("client_admin", "client_contributor", "third_party")


def _matrix(module: str) -> dict[str, dict[str, str]]:
    doc = yaml.safe_load((ROOT / f"docs/architecture/permission-matrix/{module}.yaml").read_text())
    return cast(dict[str, dict[str, str]], doc["actions"])


def _human_only() -> set[str]:
    rows = yaml.safe_load((ROOT / "docs/architecture/human-only-actions.yaml").read_text())
    return {row["action"] for row in cast(list[dict[str, str]], rows["actions"])}


# --- A-04-T25: internal control -------------------------------------------------------------


@pytest.mark.parametrize("action", ["control.edit", "exception.route"])
def test_a04t25_control_writes_refuse_the_agent_system_and_clients(action: str) -> None:
    row = _matrix("assurance")[action]
    assert row.get("agent", "deny") == "deny"
    assert row.get("system", "deny") == "deny"
    assert all(row.get(p, "deny") == "deny" for p in CLIENTS)


def test_a04t25_routing_without_a_registered_route_is_503_not_a_silent_drop() -> None:
    source = (MOD / "assurance/internal_control.py").read_text()
    assert "route_not_available" in source
    assert "503" in source or "Unavailable" in source


def test_a04t25_an_agents_severity_is_a_suggestion_by_schema() -> None:
    migration = next((BACKEND / "migrations/versions").glob("0657_*.py")).read_text()
    assert "CHECK (proposed_severity IS NULL OR proposed_by_kind IS NOT NULL)" in migration
    assert (
        "proposed_by_kind IS DISTINCT FROM 'human' OR proposed_by_user_id IS NOT NULL" in migration
    )


# --- A-06-T13: completion decision kinds -----------------------------------------------------


def _kind_blocks(source: str) -> list[str]:
    return re.findall(r"DecisionKind\((.*?)\)\s*\)", source, flags=re.S)


@pytest.mark.parametrize("constant", ["SEVERITY_KIND", "SUM_KIND"])
def test_a06t13_each_kind_is_reserved_to_the_engagement_partner(constant: str) -> None:
    source = (MOD / "assurance/completion_decisions.py").read_text()
    blocks = [b for b in _kind_blocks(source) if f"code={constant}" in b]
    assert blocks, constant
    assert all('reserved_role="engagement_partner"' in b for b in blocks)


def test_a06t13_concluding_is_human_only_at_the_data_layer() -> None:
    assert {"deficiency.concluded", "sum.concluded"} <= _human_only()


# --- A-06-T19: statements v1 ----------------------------------------------------------------


def test_a06t19_versions_and_their_parts_are_insert_only() -> None:
    assert {
        "statement_versions",
        "line_items",
        "linked_values",
        "tie_out_runs",
        "statement_approvals",
    } <= reporting_registry.INSERT_ONLY
    assert reporting_registry.INSERT_ONLY <= reporting_registry.TABLES


@pytest.mark.parametrize(
    "action",
    ["statement.draft", "statement.send_draft", "statement.record_management_approval"],
)
def test_a06t19_statement_writes_refuse_clients_and_the_agent(action: str) -> None:
    row = _matrix("reporting")[action]
    assert all(row.get(p, "deny") == "deny" for p in CLIENTS)
    assert row.get("agent", "deny") != "allow"


# --- T-03-T02 / T-03-T04: extensions, estimates and the payments engine --------------------


@pytest.mark.parametrize(
    "action",
    [
        "filing_extension.prepare",
        "filing_extension.approve_payment",
        "filing_extension.mark_filed",
        "estimate_schedule.update",
    ],
)
def test_t03_tax_writes_refuse_clients_and_the_agent(action: str) -> None:
    row = _matrix("tax")[action]
    assert all(row.get(p, "deny") == "deny" for p in CLIENTS)
    assert row.get("agent", "deny") != "allow"


def test_t03t04_the_engine_rounds_half_up_through_the_kernel() -> None:
    tree = ast.parse((MOD / "tax/compute/payments.py").read_text())
    floats = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "float"
    ]
    assert floats == []  # money never passes through float (ADR-050)
    assert quantize_half_up(Decimal("1.005"), 2) == Decimal("1.01")
    assert quantize_half_up(Decimal("-1.005"), 2) == Decimal("-1.01")


def test_t03t04_the_compute_package_imports_only_kernel_numeric_and_calendar() -> None:
    tree = ast.parse((MOD / "tax/compute/payments.py").read_text())
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    abacus = {m for m in imported if m.startswith("abacus.")}
    assert abacus <= {"abacus.kernel.numeric", "abacus.kernel.calendar"}, abacus
