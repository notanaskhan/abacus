"""C-01-T02 (TASK-8002; C-01 §4.3, §4.8; SPEC-655 AC-54): the S44 protected bundle.

Held from the generated files themselves: every human verb denies the agent, the system, support
and portal principals; reads give the agent only its task scope; the portal holds only the two
transaction-question actions; the four flags are off by default; `closes` is a module."""

from __future__ import annotations

import pytest

from abacus.kernel import _flags
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.platform.entitlements import MODULES, REVIEWED_MODULES

READS = ("close.read", "close_plan.read", "flux.read", "ledger.read")
HUMAN_VERBS = (
    "close.assign",
    "close.status_move",
    "close_run.start",
    "close_run.retry",
    "close_plan.edit",
    "close_plan.request_publish",
    "close_plan.publish",
    "close_plan.draft_from_history",
    "close_template.import",
    "arrangement.edit",
    "reconciliation.resolve_item",
    "flux.explain",
    "flux.edit",
    "flux.accept",
    "transaction_question.send",
    "ledger.sync_now",
)
PORTAL = ("client_admin", "client_contributor", "third_party")


@pytest.mark.parametrize("action", HUMAN_VERBS)
def test_ac54_every_human_verb_denies_the_agent_the_system_support_and_portal(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "deny"
    assert cells["system"] == "deny"
    for role in (*PORTAL, "platform_support", "platform_support_content"):
        assert cells.get(role, "deny") == "deny", (action, role)


@pytest.mark.parametrize("action", READS)
def test_reads_give_the_agent_only_its_task_scope(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "task_scope"
    for role in PORTAL:
        assert cells.get(role, "deny") == "deny", (action, role)


def test_the_agent_keeps_only_its_three_task_scoped_writes() -> None:
    assert ACTIONS["suggestion.create"]["agent"] == "task_scope"
    assert ACTIONS["issue.create"]["agent"] == "task_scope"
    assert ACTIONS["decision_card.raise"]["agent"] == "task_scope"


@pytest.mark.parametrize("action", ["close.create"])
def test_generating_closes_is_a_manager_or_the_system(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "deny"
    assert cells["system"] == "allow"  # ENG-03's monthly-close step generates the 12 closes
    assert cells.get("senior", "deny") == "deny"


def test_only_managers_and_partners_publish_and_accept() -> None:
    for action in ("close_plan.publish", "flux.accept"):
        cells = ACTIONS[action]
        assert cells["engagement_partner"] == "allow"
        assert cells["manager"] == "allow"
        assert cells.get("senior", "deny") == "deny", action


def test_the_portal_holds_only_its_two_question_actions_inside_its_grant() -> None:
    for action in ("transaction_question.read_own", "transaction_question.answer"):
        cells = ACTIONS[action]
        assert cells["client_admin"] == "allow"
        assert cells["client_contributor"] == "allow"
        assert cells["agent"] == "deny"
        assert cells["scope_only"] == "required"
        for role in ("engagement_partner", "manager", "senior", "staff"):
            assert cells.get(role, "deny") == "deny", (action, role)


def test_qc3_staff_cannot_start_runs_until_the_per_role_condition_exists() -> None:
    assert ACTIONS["close_run.start"].get("staff", "deny") == "deny"


def test_the_four_flags_are_registered_off_by_default() -> None:
    for flag in (
        _flags.CLOSES_ENGINE,
        _flags.CLOSES_PORTAL_REQUESTS,
        _flags.CLOSES_AGENT,
        _flags.CONNECTIONS_LEDGER_SYNC,
    ):
        assert flag.kind == "boolean"
        assert flag.default == "false"


def test_closes_is_a_module_entitlement_without_a_review() -> None:
    assert "closes" in MODULES
    assert "closes" not in REVIEWED_MODULES
