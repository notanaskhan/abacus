"""T-05-T04 (TASK-6730; T-05 §4.3, F13; ADR P-28): the S35 protected bundle.

Row acceptance: "The bundle merges first in S35, generated matrix tests show agent deny on every
human verb, and make check-fast is green." Held here from the generated files themselves."""

from __future__ import annotations

import pytest

from abacus.kernel import _flags
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.platform.entitlements import MODULES, REVIEWED_MODULES

READS = ("workbook.read", "allocation_structure.read", "tax_memo.read", "tax_reconciliation.read")
HUMAN_VERBS = (
    "workbook.edit",
    "workbook.export",
    "workbook_import.create",
    "workbook_run.start",
    "tax_ownership.edit",
    "allocation_structure.edit",
    "tax_memo.edit",
    "tax_memo.draft",
)
NOBODY_ELSE = (
    "client_admin",
    "client_contributor",
    "third_party",
    "platform_support",
    "platform_support_content",
)


@pytest.mark.parametrize("action", HUMAN_VERBS)
def test_ac_every_human_verb_denies_the_agent_the_system_support_and_portal(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "deny"
    assert cells["system"] == "deny"
    for role in NOBODY_ELSE:
        assert cells[role] == "deny", (action, role)
    assert "independence" not in cells  # independence is not required for tax (T-05 §4.3)


@pytest.mark.parametrize("action", READS)
def test_reads_give_the_agent_only_its_task_scope(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "task_scope"
    for role in NOBODY_ELSE:
        assert cells[role] == "deny", (action, role)


def test_the_export_needs_a_fresh_mfa_and_a_review_function() -> None:
    cells = ACTIONS["workbook.export"]
    assert cells["mfa_recent"] == "required"
    assert set(cells["function_in"].split(",")) == {
        "detail_reviewer",
        "manager_reviewer",
        "signer",
    }


def test_the_three_flags_are_registered_off_by_default() -> None:
    for flag in (_flags.TAX_ENTITY_WORKSPACE, _flags.TAX_WORKBOOK_RUN, _flags.TAX_ENTITY_AGENTS):
        assert flag.kind == "boolean"
        assert flag.default == "false"


def test_the_entitlement_requires_review() -> None:
    assert "tax_entity_returns" in MODULES
    assert "tax_entity_returns" in REVIEWED_MODULES
