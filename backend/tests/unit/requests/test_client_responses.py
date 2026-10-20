"""SPEC-042 (TASK-106): only the client responds or marks the list done; the firm reads."""

from __future__ import annotations

from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.requests.client_responses import REASONS


def test_ac1_only_client_roles_respond() -> None:
    decisions = RULES["client_item.respond"].decisions
    assert decisions.get("client_admin") == "client_visible_only"
    assert decisions.get("client_contributor") == "assigned_only"
    for firm in ("engagement_partner", "manager", "senior", "staff", "agent"):
        assert decisions.get(firm) in (None, "deny")


def test_ac4_only_the_client_admin_marks_the_list_done() -> None:
    decisions = RULES["client_list.mark_done"].decisions
    assert decisions.get("client_admin") == "allow"
    assert decisions.get("client_contributor") in (None, "deny")


def test_ac1_the_three_reasons() -> None:
    assert REASONS == ("not_this_year", "sent_another_way", "dont_have")
