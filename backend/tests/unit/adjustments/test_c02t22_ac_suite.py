"""ac-test-author ayushkbhatia

C-02-T22 (TASK-8710; ADR-078; SPEC-700, SPEC-701): AC suite 1 on the close approvals and posting,
written from the row and C-02 §3, not from the diff. Row acceptance: "the agent and system
principals are denied every approval, posting, release, hand-off and filing action at matrix
level". Covered:

- I-AGENT-NEVER, generated: every C-02 human action in adjustments.yaml, closes.yaml,
  integrations.yaml and connections.yaml denies `agent` and `system` (the policy principal holds
  none);
- a batch within policy needs an approver level the engagement role meets (unknown roles never);
- every posting and approval route refuses a non-person at its first gate (INV-1);
- a posting batch for an attest client is refused before anything is written (ADR-344 §4), and the
  W1 gate refuses an attest client first among its switches.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.adjustments import close_approvals

REPO = Path(__file__).resolve().parents[4]
MATRIX = REPO / "docs" / "architecture" / "permission-matrix"
SRC = REPO / "backend" / "src" / "abacus" / "modules"

C02_ADJUSTMENTS = (
    "proposed_entry.approve", "proposed_entry.request_approval", "proposed_entry.undo_approval",
    "proposed_entry.withdraw_approval", "proposed_entry.reject_close",
    "proposed_entry.record_external", "proposed_entry.export", "posting_batch.dry_run",
    "posting_batch.post", "closing_date_conflict.resolve", "approval_batch.create",
)  # fmt: skip
C02_CLOSES = (
    "close_package.edit", "close_package.generate", "close_package.export",
    "close_package.release", "close.lock", "close.reopen", "tax_handoff.publish",
    "vendor_1099.update", "w9.request", "tin_match.record", "backup_withholding.record",
    "information_return_batch.approve", "information_return_batch.export",
    "information_return_batch.record_filing", "information_return_batch.record_ack",
)  # fmt: skip
C02_INTEGRATIONS = (
    "write_capability.execute", "write_capability.enable", "gl_posting_settings.update",
)  # fmt: skip
C02_CONNECTIONS = ("ledger_connection.export", "connection.grant_write", "connection.revoke_write")
NEVER = ("agent", "system")


def _actions(name: str) -> dict[str, dict[str, object]]:
    data = cast(
        dict[str, dict[str, object]],
        yaml.safe_load((MATRIX / f"{name}.yaml").read_text(encoding="utf-8")),
    )
    return {k: cast(dict[str, object], v) for k, v in (data.get("actions") or {}).items()}


CASES = (
    [("adjustments", a) for a in C02_ADJUSTMENTS]
    + [("closes", a) for a in C02_CLOSES]
    + [("integrations", a) for a in C02_INTEGRATIONS]
    + [("connections", a) for a in C02_CONNECTIONS]
)


@pytest.mark.parametrize(("file", "action"), CASES, ids=[f"{f}:{a}" for f, a in CASES])
def test_ac1_the_agent_and_the_system_are_denied_every_c02_action(file: str, action: str) -> None:
    row = _actions(file).get(action)
    assert row is not None, f"{action} is missing from {file}.yaml"
    for principal in NEVER:
        assert row.get(principal) == "deny", f"{action} must deny {principal}"
    assert row.get("policy_principal") in (None, "deny")


def test_ac2_an_approver_level_is_met_only_by_its_engagement_roles() -> None:
    assert not close_approvals.meets(None, "senior")
    assert not close_approvals.meets("agent", "senior")
    assert not close_approvals.meets("intern", "manager")


def _first_await(fn: ast.AsyncFunctionDef) -> str | None:
    for node in ast.walk(fn):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            func = node.value.func
            return func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    return None


ROUTE_FILES = (SRC / "adjustments" / "posting_contract.py",)
HUMAN_ROUTES = (
    "approve_entry_route", "posting_request_approval_route", "undo_approval_route",
    "withdraw_approval_route", "reject_close_entry_route", "record_external_route",
    "dry_run_route", "post_batch_route", "undo_batch_route", "retry_entry_route",
)  # fmt: skip


@pytest.mark.parametrize("route", HUMAN_ROUTES)
def test_ac3_every_posting_and_approval_route_refuses_a_non_person_first(route: str) -> None:
    tree = ast.parse(ROUTE_FILES[0].read_text(encoding="utf-8"))
    found = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == route),
        None,
    )
    assert found is not None, route
    assert _first_await(found) == "_human"


def test_ac4_an_attest_batch_is_refused_before_anything_is_written() -> None:
    source = (SRC / "adjustments" / "posting.py").read_text(encoding="utf-8")
    create = source[source.index("async def create_batch") :]
    refuse = create.index("AttestClientPostingRefused")
    assert refuse < create.index("async with uow(")
    gate = (SRC / "integrations" / "writes.py").read_text(encoding="utf-8")
    refusal = gate[gate.index("async def w1_refusal") :]
    assert refusal.index("attest_client_posting_refused") < refusal.index("entry.enabled")
