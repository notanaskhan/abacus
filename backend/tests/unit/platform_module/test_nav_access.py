"""P-01-T04 (AC 2.1.2): the SHL-03 admin rows come from the matrix, through `nav`."""

from __future__ import annotations

from abacus.modules.identity.api import RULES
from abacus.modules.platform.capabilities import nav_access


def test_a_firm_admin_writes_settings_and_users_and_reads_the_audit_log() -> None:
    nav = nav_access(
        frozenset(
            {"firm.manage_settings", "firm.read_settings", "firm.manage_users", "audit_event.read"}
        )
    )
    assert nav == {
        "firm_settings": "write",
        "users_roles": "write",
        "audit_log": "read",
        "security_center": "none",
        "developer_api": "none",
    }


def test_a_partner_reads_settings_and_the_audit_log_only() -> None:
    nav = nav_access(frozenset({"firm.read_settings", "audit_event.read"}))
    assert nav["firm_settings"] == "read"
    assert nav["users_roles"] == "none"
    assert nav["audit_log"] == "read"


def test_a_manager_sees_no_admin_row() -> None:
    assert set(nav_access(frozenset({"engagement.read_metadata"})).values()) == {"none"}


def test_partners_hold_read_settings_in_the_matrix_and_developer_api_maps_to_nothing() -> None:
    assert RULES["firm.read_settings"].decisions.get("firm_partner") == "allow"
    assert "developer.read" not in RULES
