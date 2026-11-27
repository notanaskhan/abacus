"""T-07-T03 (TASK-8017; T-07 §4.4, §4.7; SPEC-656 AC-15.1; DEC-5007): the S44 trusts-and-estates
protected bundle.

Row acceptance: "the generated matrix test denies the agent principal every edit, approve, reopen,
record, release and send action." Held here from the generated files themselves."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus.modules.tax import estate_contract, fiduciary_contract

READS = (
    "instrument.read",
    "fiduciary_computation.read",
    "beneficiary_allocation.read",
    "fiduciary_election.read",
    "estate_workpaper.read",
)
HUMAN_VERBS = (
    "instrument.attach",
    "instrument.read_run",
    "instrument_determination.edit",
    "instrument_interpretation.reopen",
    "fai_line.edit",
    "trust_distribution.edit",
    "fiduciary_computation.recompute",
    "fiduciary_computation.export",
    "fiduciary_election.record",
    "estate_workpaper.edit",
)
PORTAL = ("client_admin", "client_contributor", "third_party")


@pytest.mark.parametrize("action", HUMAN_VERBS)
def test_ac15_1_every_write_denies_the_agent_the_system_and_the_portal(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "deny"
    assert cells["system"] == "deny"
    for role in PORTAL:
        assert cells.get(role, "deny") == "deny", (action, role)
    assert "platform_support" not in cells and "platform_support_content" not in cells


@pytest.mark.parametrize("action", READS)
def test_reads_give_the_agent_only_its_task_scope_and_the_portal_nothing(action: str) -> None:
    cells = ACTIONS[action]
    assert cells["agent"] == "task_scope"
    for role in (*PORTAL, "platform_support", "platform_support_content"):
        assert cells[role] == "deny", (action, role)


def test_reopen_and_the_election_are_a_manager_or_partner_act() -> None:
    for action in ("instrument_interpretation.reopen", "fiduciary_election.record"):
        allowed = {role for role, cell in ACTIONS[action].items() if cell == "allow"}
        assert allowed == {"engagement_partner", "manager"}, action


def test_determination_and_distribution_edits_exclude_the_partner() -> None:
    # T-07 §4.4: staff, senior, reviewer and manager edit with a reason; the partner approves.
    for action in ("instrument_determination.edit", "trust_distribution.edit", "fai_line.edit"):
        allowed = {role for role, cell in ACTIONS[action].items() if cell == "allow"}
        assert allowed == {"manager", "senior", "staff", "reviewer"}, action


def test_the_three_flags_retired_into_the_tax_returns_entitlement() -> None:
    # T-06-T69 (DEC-6024): gone from the registry; the routes read `tax_returns` instead.
    retired = {"tax.fiduciary_workpapers", "tax.fiduciary_k1_release", "tax.estate_workpapers"}
    assert not retired & set(_flags.FLAGS)


@pytest.mark.parametrize("gate", ["fiduciary", "estate"])
@pytest.mark.parametrize("held", [False, True])
def test_the_t07_routes_answer_404_without_the_entitlement(
    monkeypatch: pytest.MonkeyPatch, gate: str, held: bool
) -> None:
    """T-06-T69: the entitlement-off test that replaces the retired flags' flag-off test."""
    asked: list[str] = []

    async def entitlement(_tenant: object, module: str) -> object | None:
        asked.append(module)
        return object() if held else None

    module = fiduciary_contract if gate == "fiduciary" else estate_contract
    monkeypatch.setattr(module, "entitlement", entitlement)
    ctx = AuthContext(TenantContext(uuid.uuid4(), "human", "u"), uuid.uuid4(), uuid.uuid4(),
                      None, None)  # fmt: skip
    check = (
        fiduciary_contract._entitled(ctx)  # pyright: ignore[reportPrivateUsage] -- the gate under test
        if gate == "fiduciary"
        else estate_contract._flag_on(ctx)  # pyright: ignore[reportPrivateUsage] -- the gate under test
    )
    if held:
        asyncio.run(check)
    else:
        with pytest.raises(NotFound):
            asyncio.run(check)
    assert asked == ["tax_returns"]
