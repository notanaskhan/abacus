"""Independent AC tests for A-04-T07, T18 and T19 (A-04-T30; ADR-078; A-04 §3.1, §3.2, §3.5).

Written apart from those tasks and without editing their tests: tailoring refuses a mandatory
step (T07), the three planning decision kinds are reserved to the engagement partner and their
decisions are human-only (T18), G4 is answered by `g4_facts` (T18), the fraud minutes are the
engagement partner's alone with every other principal refused at the matrix and the approval
human-only at the data layer (T19), and the management inquiry is a questionnaire draft that
code never sends (T19). Client principals are denied every A-04 write (INV-4).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.kernel import _human_only_actions as generated

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
MOD = BACKEND / "src/abacus/modules"
HUMAN_ONLY = cast(
    list[dict[str, str]],
    yaml.safe_load((ROOT / "docs/architecture/human-only-actions.yaml").read_text())["actions"],
)
MATRIX = cast(
    dict[str, dict[str, str]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/assurance.yaml").read_text())[
        "actions"
    ],
)
CLIENTS = ("client_admin", "client_contributor", "third_party")


def _human_only() -> set[str]:
    return {row["action"] for row in HUMAN_ONLY}


def test_tailoring_refuses_a_mandatory_step() -> None:
    source = (MOD / "workpapers/procedures.py").read_text()
    assert 'code = "mandatory_step"' in source


def _kind_blocks(source: str) -> list[str]:
    return re.findall(r"DecisionKind\((.*?)\)\s*\)", source, flags=re.S)


@pytest.mark.parametrize(
    ("path", "constant"),
    [
        ("assurance/materiality.py", "PROPOSE_KIND"),
        ("assurance/materiality.py", "REASSESS_KIND"),
        ("assurance/risks.py", "APPROVAL_KIND"),
    ],
)
def test_the_three_decision_kinds_are_the_engagement_partners(path: str, constant: str) -> None:
    blocks = [b for b in _kind_blocks((MOD / path).read_text()) if f"code={constant}" in b]
    assert blocks, constant
    assert all('reserved_role="engagement_partner"' in b for b in blocks)


def test_a_decision_on_any_card_is_human_only() -> None:
    assert {"decision.decided", "decision.reassessed"} <= _human_only()


def test_g4_is_answered_by_g4_facts() -> None:
    source = (MOD / "assurance/gates.py").read_text()
    assert 'register_gate_provider("G4", g4_facts)' in source


def test_fraud_minutes_are_the_engagement_partners_alone() -> None:
    row = MATRIX["fraud_minutes.approve"]
    allowed = {principal for principal, rule in row.items() if rule == "allow"}
    assert allowed == {"engagement_partner"}
    for refused in ("agent", "system", "client_service", *CLIENTS):
        assert row[refused] == "deny", refused
    for staff in ("staff", "senior", "manager"):
        assert row.get(staff, "deny") != "allow", staff


def test_the_minutes_approval_is_human_only_at_the_data_layer() -> None:
    assert "fraud_minutes.approved" in _human_only()
    assert "fraud_minutes.approved" in generated.HUMAN_ONLY_ACTIONS


def test_code_never_sends_the_management_inquiry() -> None:
    tree = ast.parse((MOD / "assurance/fraud_brainstorm.py").read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "abacus.modules.requests.api"
        for alias in node.names
    }
    assert imported <= {"create_questionnaire", "questionnaire"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not {c for c in called if "send" in c.lower()}


@pytest.mark.parametrize(
    "action",
    [
        a
        for a in MATRIX
        if a.split(".", 1)[0] in {"risk", "fraud_minutes", "materiality", "fraud_brainstorm"}
        and not a.endswith(".read")
    ],
)
def test_client_principals_are_denied_every_a04_write(action: str) -> None:
    row = MATRIX[action]
    for principal in CLIENTS:
        assert row.get(principal, "deny") == "deny", (action, principal)
