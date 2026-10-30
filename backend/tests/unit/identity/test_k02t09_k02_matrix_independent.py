# ac-test-author: ayushkbhatia
"""K-02-T09 (TASK-2211; ADR-078): independent acceptance tests for N's red work in K-02-T01, the
matrix rows and the `owner_of_target` condition (DEC-1150), written from K-02 §4.4, §6 and the
contract (`docs/contracts/rules-tables.md`), not from the implementing suites.

- The `owner_of_target` truth table: only a person who is the target's owner (and a partner now)
  meets it; an agent or a system run never does, whatever its facts say; unknown fails closed.
- The agent, the system and both portal roles are denied every K-02 write in the matrix, and an
  agent run holding every K-02 write in its scope is still refused each one by `authorise`.
- Reference sets have no write action and no write route: the operator CLI is the only writer.

The suite fails if any K-02 write allows the agent principal.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    TargetFacts,
    authorise,
)
from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.repository import FirmRole

K02_WRITES = (
    "firm_standard.create",
    "firm_standard.assign_owner",
    "firm_standard.draft",
    "firm_standard.import",
    "firm_standard.publish",
)
K02_READS = ("firm_standard.read", "reference_set.read", "due_date.read")
OWNER_ACTIONS = ("firm_standard.draft", "firm_standard.publish")
NON_PERSONS = ("agent", "system", "client_admin", "client_contributor")


@pytest.mark.parametrize("action", K02_WRITES)
@pytest.mark.parametrize("principal", NON_PERSONS)
def test_every_k02_write_denies_the_agent_the_system_and_the_portal(
    action: str, principal: str
) -> None:
    assert RULES[action].decisions.get(principal) == "deny", (action, principal)


@pytest.mark.parametrize("action", K02_READS)
def test_the_portal_reads_no_k02_record(action: str) -> None:
    decisions = RULES[action].decisions
    assert (
        decisions.get("client_admin") == "deny" and decisions.get("client_contributor") == "deny"
    )
    assert decisions.get("system") == "deny"


@pytest.mark.parametrize("action", OWNER_ACTIONS)
def test_the_owner_actions_carry_owner_of_target_and_publish_needs_fresh_mfa(action: str) -> None:
    rule = RULES[action]
    assert rule.owner_of_target
    assert rule.mfa_recent is (action == "firm_standard.publish")
    # Only partners hold them at all (the owner must be a partner member now).
    allowed = {role for role, decision in rule.decisions.items() if decision == "allow"}
    assert allowed == {"firm_partner"}


@pytest.mark.parametrize("action", OWNER_ACTIONS)
@pytest.mark.parametrize(
    ("person", "owner", "holds"),
    [
        (True, True, True),
        (True, False, False),
        (True, None, False),  # unknown: fail closed
        (False, True, False),  # an agent or a system run never meets a target condition
        (False, False, False),
        (False, None, False),
    ],
)
def test_owner_of_target_truth_table(
    action: str, person: bool, owner: bool | None, holds: bool
) -> None:
    assert conditions_hold(RULES[action], ConditionFacts(owner=owner), person=person) is holds


def test_no_other_action_carries_owner_of_target() -> None:
    carrying = {action for action, rule in RULES.items() if rule.owner_of_target}
    assert carrying == set(OWNER_ACTIONS)


def test_reference_sets_have_no_write_action_and_no_write_route() -> None:
    assert not [a for a in RULES if a.startswith("reference_set.") and a != "reference_set.read"]
    paths = cast(dict[str, dict[str, object]], json.loads(document())["paths"])
    for path, ops in paths.items():
        if path.startswith(("/v1/reference-sets", "/v1/due-dates")):
            assert set(ops) == {"get"}, path


@pytest.fixture
def _no_walls(monkeypatch: pytest.MonkeyPatch) -> None:
    async def walled(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    monkeypatch.setattr(authz, "walled_clients", walled)


def _agent(initiator_role: str) -> AgentContext:
    user = uuid.uuid4()
    tenant = TenantContext(uuid.uuid4(), "human", str(user))
    initiator = AuthContext(
        tenant, user, uuid.uuid4(), cast(FirmRole | None, initiator_role), None
    )
    run_id = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(tenant.tenant_id, "agent", f"agent:probe:{run_id}"),
        agent_id="probe",
        agent_run_id=run_id,
        engagement_id=None,
        task_scope=frozenset(K02_WRITES),
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


@pytest.mark.usefixtures("_no_walls")
@pytest.mark.parametrize("action", K02_WRITES)
@pytest.mark.parametrize("initiator", ["practice_leader", "quality_partner"])
async def test_an_agent_run_is_refused_every_k02_write_even_in_scope(
    action: str, initiator: str
) -> None:
    agent = _agent(initiator)
    resource = Resource.firm(agent.tenant_id)
    if action in OWNER_ACTIONS:
        # Even named as the owner, an agent never meets `owner_of_target`.
        resource = replace(resource, target=TargetFacts(owner_user_id=agent.initiator.user_id))
    with pytest.raises(Forbidden):
        await authorise(agent, action, resource)
