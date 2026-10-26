"""G-02-T02 (SPEC-349 §9, AC-45, AC-46): the firm-governance actions in the permission matrix.

Every new action denies the agent and the system (I-AGENT-NEVER at the matrix) and no client
principal holds any of them; the widened rows keep their old holders and gain the new ones; the
four flags exist and default off; the platform's audit slots fail closed."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping, Sequence

import pytest

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.platform import audit_slots
from abacus.modules.platform.audit_slots import AuditEventRef, AuditLabel, AuditValues

NEW_ACTIONS = (
    "audit_event.export",
    "security.read",
    "security.manage",
    "session.end",
    "staff.unlock",
    "incident.read",
    "incident.decide",
    "firm_export.schedule",
    "ai_policy.read",
    "ai_policy.draft",
    "ai_policy.publish",
    "ai_policy.approve",
)
WIDENED = (
    "audit_event.read",
    "support_session.read",
    "support_session.manage",
    "firm_agents.pause",
)
CLIENT_ROLES = ("client_admin", "client_contributor")


@pytest.mark.parametrize("action", NEW_ACTIONS + WIDENED)
def test_ac45_ac46_agent_system_and_clients_never_hold_a_governance_action(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)
    for role in CLIENT_ROLES:
        assert decisions.get(role, "deny") == "deny", (action, role)


def test_the_widened_rows_keep_their_holders_and_gain_the_new_ones() -> None:
    read = RULES["audit_event.read"].decisions
    assert read["security_admin"] == "allow"
    assert read["practice_leader"] == "in_scope"
    assert {read["engagement_partner"], read["manager"], read["firm_admin"]} == {"allow"}
    assert read["quality_partner"] == "in_scope"
    for action in ("support_session.read", "support_session.manage"):
        assert RULES[action].decisions["firm_admin"] == "allow"
        assert RULES[action].decisions["security_admin"] == "allow"
    pause = RULES["firm_agents.pause"].decisions
    assert {pause["firm_admin"], pause["security_admin"], pause["quality_partner"]} == {"allow"}


def test_ac37_publishing_is_the_qm_owners_and_approving_a_partners() -> None:
    publish = RULES["ai_policy.publish"].decisions
    assert {r for r, d in publish.items() if d == "allow"} == {"quality_partner"}
    approve = RULES["ai_policy.approve"].decisions
    assert {r for r, d in approve.items() if d == "allow"} == {"firm_partner"}
    assert RULES["ai_policy.publish"].mfa_recent and RULES["ai_policy.approve"].mfa_recent


def test_the_four_flags_exist_and_default_off() -> None:
    names = {"audit_log.explorer", "audit_log.values", "security_center.v1", "ai_policy.v1"}
    for flag in (
        _flags.AUDIT_LOG_EXPLORER,
        _flags.AUDIT_LOG_VALUES,
        _flags.SECURITY_CENTER_V1,
        _flags.AI_POLICY_V1,
    ):
        assert flag.name in names
        assert flag.default == "false"


def _viewer() -> AuthContext:
    tenant = TenantContext(uuid.uuid4(), "human", str(uuid.uuid4()))
    return AuthContext(tenant, uuid.uuid4(), uuid.uuid4(), "security_admin", None)


_EVENT = AuditEventRef(1, "wall.created", "g02_probe_unregistered", str(uuid.uuid4()), None, None)


def test_an_unregistered_type_has_no_label_and_its_values_are_unavailable() -> None:
    viewer = _viewer()
    assert asyncio.run(audit_slots.audit_labels(viewer, "g02_probe_unregistered", ["1"])) == {}
    assert asyncio.run(audit_slots.audit_values(viewer, _EVENT)).status == "unavailable"


def test_a_failing_resolver_answers_unavailable_and_restricted_labels_are_refused() -> None:
    async def labeler(viewer: AuthContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
        return {"1": AuditLabel("Copperleaf", "confidential"), "2": AuditLabel("x", "restricted")}

    async def resolver(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
        raise RuntimeError("boom")

    audit_slots.register_audit_labeler("g02_probe_failing", labeler)
    audit_slots.register_audit_value_resolver("g02_probe_failing", resolver)
    viewer = _viewer()
    labels = asyncio.run(audit_slots.audit_labels(viewer, "g02_probe_failing", ["1", "2"]))
    assert set(labels) == {"1"}
    event = AuditEventRef(2, "wall.created", "g02_probe_failing", "1", None, None)
    assert asyncio.run(audit_slots.audit_values(viewer, event)).status == "unavailable"
    with pytest.raises(ValueError):
        audit_slots.register_audit_labeler("g02_probe_failing", labeler)
