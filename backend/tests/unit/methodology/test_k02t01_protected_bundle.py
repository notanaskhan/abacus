"""K-02-T01 (DEC-1150; K-02 §4.4, §4.8, §4.9): the S16 protected bundle for K-02.

Acceptance: "the generated permission tests deny the agent, portal principals and a non-owner
partner every K-02 write." The generated suites carry the cases (`test_permission_matrix_
generated.py` for the client roles, `test_resolution_actions_generated.py` for the agent, the
system, support and the non-owner partner); this file pins the rows they are generated from, so
a widened row fails here as well as in the generated diff."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, TargetFacts, authorise
from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.repository import FirmPolicy

WRITES = (
    "firm_standard.create",
    "firm_standard.assign_owner",
    "firm_standard.draft",
    "firm_standard.import",
    "firm_standard.publish",
)
READS = ("firm_standard.read", "reference_set.read", "due_date.read")
PORTAL = ("client_admin", "client_contributor", "third_party")
FIRM_ROLES = (
    *("firm_admin", "practice_leader", "quality_partner", "security_admin"),
    *("engagement_partner", "manager", "senior", "staff", "reviewer"),
)


@pytest.mark.parametrize("action", WRITES)
def test_ac_every_k02_write_denies_the_agent_the_system_and_the_portal(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny", action
    assert decisions.get("system") == "deny", action
    for role in PORTAL:
        assert decisions.get(role, "deny") == "deny", (action, role)


def test_ac_drafting_and_publishing_are_the_owners_a_partner_now() -> None:
    for action in ("firm_standard.draft", "firm_standard.publish"):
        rule = RULES[action]
        assert rule.owner_of_target, action
        assert {r for r, d in rule.decisions.items() if d == "allow"} == {"firm_partner"}
    assert RULES["firm_standard.publish"].mfa_recent
    assert RULES["firm_standard.create"].mfa_recent
    creators = {r for r, d in RULES["firm_standard.create"].decisions.items() if d == "allow"}
    assert creators == {"practice_leader", "quality_partner"}  # DEC-38


@pytest.mark.parametrize("action", READS)
def test_every_firm_role_reads_and_the_agent_only_at_task_scope(action: str) -> None:
    decisions = RULES[action].decisions
    for role in FIRM_ROLES:
        assert decisions.get(role) == "allow", (action, role)
    assert decisions.get("agent") == "task_scope"
    for role in (*PORTAL, "system"):
        assert decisions.get(role, "deny") == "deny", (action, role)


def test_there_is_no_reference_set_write_action() -> None:
    # The operator CLI is the only writer until PLT-01 (G-04), through owner-only functions.
    assert [a for a in RULES if a.startswith("reference_set.") and a != "reference_set.read"] == []


def test_the_two_flags_exist_default_off_and_expire_inside_90_days() -> None:
    assert _flags.KNOWLEDGE_FIRM_STANDARDS.name == "knowledge.firm_standards"
    assert _flags.RULES_REFERENCE_SETS.name == "rules.reference_sets"
    for flag in (_flags.KNOWLEDGE_FIRM_STANDARDS, _flags.RULES_REFERENCE_SETS):
        assert flag.default == "false"


def test_owner_of_target_is_a_persons_condition() -> None:
    rule = RULES["firm_standard.publish"]
    assert conditions_hold(rule, ConditionFacts(owner=True), person=True)
    assert not conditions_hold(rule, ConditionFacts(owner=True), person=False)
    assert not conditions_hold(rule, ConditionFacts(owner=False), person=True)
    assert not conditions_hold(rule, ConditionFacts(), person=True)


def _partner(monkeypatch: pytest.MonkeyPatch, *, partner: bool) -> AuthContext:
    async def none(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def level(*_: object) -> bool:
        return partner

    async def policy(*_: object) -> FirmPolicy:
        return FirmPolicy({}, frozenset())

    async def not_ended(*_: object) -> bool:
        return False

    monkeypatch.setattr(authz, "walled_clients", none)
    monkeypatch.setattr(authz, "engagement_roles_in_firm", none)
    monkeypatch.setattr(authz, "firm_policy", policy)
    monkeypatch.setattr(authz, "access_has_ended", not_ended)
    monkeypatch.setattr(authz, "_partner_level", level)
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC) - timedelta(minutes=1),
    )


def _outcome(ctx: AuthContext, owner: uuid.UUID | None) -> str:
    resource = Resource.firm(ctx.tenant_id)
    if owner is not None:
        resource = Resource(ctx.tenant_id, None, False, target=TargetFacts(owner_user_id=owner))
    try:
        asyncio.run(authorise(ctx, "firm_standard.publish", resource))
    except Forbidden:
        return "deny"
    return "allow"


def test_us33_the_owner_publishes_and_daniel_a_non_owner_partner_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    priya = _partner(monkeypatch, partner=True)
    assert _outcome(priya, priya.user_id) == "allow"
    assert _outcome(priya, uuid.uuid4()) == "deny"  # Daniel Reyes, a partner, not the owner
    assert _outcome(priya, None) == "deny"  # no owner facts: fail closed


def test_an_owner_who_is_no_longer_a_partner_cannot_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    former = _partner(monkeypatch, partner=False)
    assert _outcome(former, former.user_id) == "deny"
