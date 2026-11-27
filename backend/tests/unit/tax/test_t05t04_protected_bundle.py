"""T-05-T04 (TASK-6730; T-05 §4.3, F13; ADR P-28): the S35 protected bundle.

Row acceptance: "The bundle merges first in S35, generated matrix tests show agent deny on every
human verb, and make check-fast is green." Held here from the generated files themselves."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.platform.entitlements import MODULES, REVIEWED_MODULES
from abacus.modules.tax import workbook_contract as wb

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
        # An unlisted role is denied; SPEC-012 keeps the support roles off write rows entirely.
        assert cells.get(role, "deny") == "deny", (action, role)
    assert "platform_support" not in cells and "platform_support_content" not in cells
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


def test_the_model_backed_flag_stays_registered_off_by_default() -> None:
    # T-06-T69 (DEC-6024): `tax.entity_workspace` and `tax.workbook_run` retired into the
    # `tax_entity_returns` entitlement; only the model-backed flag remains.
    flag = _flags.TAX_ENTITY_AGENTS
    assert flag.kind == "boolean"
    assert flag.default == "false"
    assert not {"tax.entity_workspace", "tax.workbook_run"} & set(_flags.FLAGS)


@pytest.mark.parametrize("held", [False, True])
def test_the_workbook_routes_answer_404_without_the_entitlement(
    monkeypatch: pytest.MonkeyPatch, held: bool
) -> None:
    """T-06-T69: the entitlement-off test that replaces the retired flags' flag-off test."""
    asked: list[str] = []

    async def entitlement(_tenant: object, module: str) -> object | None:
        asked.append(module)
        return object() if held else None

    monkeypatch.setattr(wb, "entitlement", entitlement)
    ctx = AuthContext(TenantContext(uuid.uuid4(), "human", "u"), uuid.uuid4(), uuid.uuid4(),
                      None, None)  # fmt: skip
    if held:
        asyncio.run(wb._flag_on(ctx))  # pyright: ignore[reportPrivateUsage] -- the gate under test
    else:
        with pytest.raises(NotFound):
            asyncio.run(wb._flag_on(ctx))  # pyright: ignore[reportPrivateUsage] -- the gate under test
    assert asked == ["tax_entity_returns"]


def test_the_entitlement_requires_review() -> None:
    assert "tax_entity_returns" in MODULES
    assert "tax_entity_returns" in REVIEWED_MODULES
