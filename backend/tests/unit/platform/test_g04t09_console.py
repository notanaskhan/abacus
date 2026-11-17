"""G-04-T09 (red): the console's staff principal and metadata-only directory (SPEC-680 AC-1 to
AC-8; DEC-5416)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.modules.identity.api import Forbidden, authorise_staff
from abacus.modules.platform import console
from abacus.modules.platform.console_contract import TenantRowOut

STAFF = uuid.uuid4()


def test_a_support_desk_role_reads_but_never_changes_entitlements() -> None:
    now = datetime.now(UTC)
    roles = frozenset({"platform_support_desk"})
    assert authorise_staff("platform_tenant.read", roles=roles, mfa_at=now, staff_id=STAFF) == (
        "platform_support_desk"
    )
    with pytest.raises(Forbidden) as denied:
        authorise_staff("platform_entitlements.update", roles=roles, mfa_at=now, staff_id=STAFF)
    assert denied.value.layer == "role"


def test_an_entitlement_change_needs_staff_mfa_within_15_minutes() -> None:
    roles = frozenset({"platform_admin"})
    stale = datetime.now(UTC) - timedelta(minutes=16)
    with pytest.raises(Forbidden) as denied:
        authorise_staff("platform_entitlements.update", roles=roles, mfa_at=stale, staff_id=STAFF)
    assert denied.value.layer == "attribute"
    fresh = datetime.now(UTC) - timedelta(minutes=5)
    assert (
        authorise_staff("platform_entitlements.update", roles=roles, mfa_at=fresh, staff_id=STAFF)
        == "platform_admin"
    )


@pytest.mark.parametrize(
    "roles", [frozenset[str](), frozenset({"firm_admin"}), frozenset({"agent"})]
)
def test_no_firm_or_unknown_role_reaches_a_console_action(roles: frozenset[str]) -> None:
    with pytest.raises(Forbidden):
        authorise_staff(
            "platform_tenant.read", roles=roles, mfa_at=datetime.now(UTC), staff_id=STAFF
        )


def test_tiles_count_the_whole_directory_and_seats_exclude_sandboxes() -> None:
    parent = uuid.uuid4()
    rows = [
        {"health": "healthy", "sandbox_of": None, "seats_used": 46, "seats_total": 46},
        {"health": "onboarding", "sandbox_of": None, "seats_used": 2, "seats_total": 10},
        {"health": "healthy", "sandbox_of": parent, "seats_used": 5, "seats_total": 5},
    ]
    t = console.tiles(rows)  # type: ignore[arg-type] -- mappings stand in for rows
    assert (t.tenants, t.healthy, t.onboarding, t.degraded) == (3, 2, 1, 0)
    assert (t.seats_used, t.seats_provisioned) == (48, 56)


def test_no_tenant_row_field_can_hold_a_client_name() -> None:
    """AC-2: metadata only; the row model has no client, contact, engagement or document field."""
    names = set(TenantRowOut.model_fields)
    assert not {
        n for n in names if any(k in n for k in ("client", "contact", "engagement", "document"))
    }


def test_the_platform_audit_keeps_a_fingerprint_not_the_reason() -> None:
    reason = "Brightwater added two Denver seniors for the busy season."
    printed = console.reason_fingerprint(reason)
    assert len(printed) == 16 and reason not in printed
