"""G-04-T02 (SPEC-680 INV-1, INV-4; SPEC-681 AC-24; DEC-5201, DEC-5202): the G-04 matrix rows.

The agent, the system, break-glass support principals and every portal principal are denied every
G-04 action; the console's staff roles hold no firm action and no firm role holds a staff action.
"""

from __future__ import annotations

import pytest

from abacus.modules.identity.authz.matrix import ROLES, RULES
from abacus.modules.identity.authz.overrides import PLATFORM_ROLES

FIRM_ACTIONS = (
    "plan.read",
    "budget_alert.manage",
    "billing_contact.manage",
    "plan_request.create",
    "plan_request.approve",
    "support.chat",
    "help.read",
    "status.read",
    "support_session.decline",
)
STAFF_ACTIONS = (
    "platform_tenant.read",
    "platform_tenant.provision",
    "platform_entitlements.update",
    "platform_support_session.request",
    "platform_support.reply",
    "platform_status.manage",
    "platform_content.read",
    "platform_content.publish",
)
STAFF_ROLES = ("platform_admin", "platform_support_desk")
NEVER = (
    "agent",
    "system",
    "client_admin",
    "client_contributor",
    "third_party",
    "link_principal",
    "platform_support",
    "platform_support_content",
)


def _allows(action: str, role: str) -> bool:
    return RULES[action].decisions.get(role, "deny") != "deny"


def test_staff_roles_are_matrix_roles_and_platform_owned() -> None:
    assert set(STAFF_ROLES) <= set(ROLES)
    assert set(STAFF_ROLES) <= PLATFORM_ROLES


@pytest.mark.parametrize("action", FIRM_ACTIONS + STAFF_ACTIONS)
def test_inv1_inv4_never_principals_are_denied(action: str) -> None:
    assert action in RULES
    for role in NEVER:
        assert not _allows(action, role), f"{role} holds {action}"


@pytest.mark.parametrize("action", FIRM_ACTIONS)
def test_staff_roles_hold_no_firm_action(action: str) -> None:
    for role in STAFF_ROLES:
        assert not _allows(action, role), f"{role} holds {action}"


@pytest.mark.parametrize("action", STAFF_ACTIONS)
def test_only_staff_roles_hold_staff_actions(action: str) -> None:
    holders = {role for role in ROLES if _allows(action, role)}
    assert holders and holders <= set(STAFF_ROLES), f"{action}: {sorted(holders)}"


def test_security_admin_never_reads_plan_and_approvers_need_fresh_mfa() -> None:
    assert not _allows("plan.read", "security_admin")  # ADM-01e
    for action in (
        "budget_alert.manage",
        "plan_request.approve",
        "platform_tenant.provision",
        "platform_entitlements.update",
        "platform_content.publish",
    ):
        assert RULES[action].mfa_recent, action
    assert {r for r in ROLES if _allows("support_session.decline", r)} == {
        "firm_admin",
        "security_admin",
    }
