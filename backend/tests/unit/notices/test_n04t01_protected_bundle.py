"""N-04-T01 (DEC-2050; N-04 §4.3, §4.7, §4.8): the S25 protected bundle for Notices.

Acceptance: "generated tests deny the agent and portal principals every notices write." The
generated suites carry the per-role cases; this file pins the rows they are generated from, so a
widened row fails here as well as in the generated diff."""

from __future__ import annotations

import pytest

from abacus.kernel import _flags
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.notifications import (
    catalogue,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the kinds
)
from abacus.modules.notifications.kinds import kind_of
from abacus_tools.codegen import feature_flags

WRITES = (
    "notice_intake.create",
    "notice_intake.update",
    "notice_intake.confirm",
    "notice.assign",
    "notice.update",
    "notice.start",
    "notice.record_as_filed",
    "notice.analyze",
    "notice.request_decision",
    "notice.note",
    "notice.agency_reply",
    "notice_response.draft",
    "notice_response.edit",
    "notice_response.send_for_signature",
    "notice_response.mark_sent",
)
READS = ("notice.read", "notice_intake.read")
PORTAL = ("client_admin", "client_contributor", "third_party")
SUPPORT = ("platform_support", "platform_support_content")
KINDS = (
    "notice_intake_ready",
    "notice_created",
    "notice_assigned",
    "notice_respond_by_soon",
    "notice_decided",
    "notice_response_ready_to_send",
    "notice_follow_up_due",
)


@pytest.mark.parametrize("action", WRITES)
def test_ac1_every_notices_write_denies_the_agent_system_support_and_the_portal(
    action: str,
) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny", action
    assert rule.decisions.get("system", "deny") == "deny", action
    for role in (*PORTAL, *SUPPORT):
        assert rule.decisions.get(role, "deny") == "deny", (action, role)
    assert rule.not_offshore, action  # DEC-2050: fail closed until an offshore alternative


@pytest.mark.parametrize("action", READS)
def test_ac1_reads_are_the_firms_and_the_agent_only_at_task_scope(action: str) -> None:
    decisions = RULES[action].decisions
    for role in ("engagement_partner", "manager", "senior", "staff", "client_service"):
        assert decisions.get(role) == "allow", (action, role)
    assert decisions.get("agent") == "task_scope"
    for role in (*PORTAL, *SUPPORT, "system"):
        assert decisions.get(role, "deny") == "deny", (action, role)


def test_ac1_deciding_is_only_p04s_and_sending_is_narrow() -> None:
    assert "notice.decide" not in RULES
    send = RULES["notice_response.send_for_signature"]
    assert {r for r, d in send.decisions.items() if d == "allow"} == {
        "engagement_partner",
        "manager",
    }
    assert send.function_in == frozenset({"manager_reviewer", "signer"})
    mark = RULES["notice_response.mark_sent"]
    assert {r for r, d in mark.decisions.items() if d == "allow"} == {
        "engagement_partner",
        "manager",
        "client_service",
    }


def test_ac1_the_two_flags_are_retired() -> None:
    # N-04-T27 (DEC-2602): no live firm held them; the stage and the gateway gate the responder.
    assert not hasattr(_flags, "NOTICES_WORKSPACE") and not hasattr(_flags, "NOTICES_RESPONDER")
    names = {entry.name for entry in feature_flags.parse(feature_flags.source())}
    assert not {"notices.workspace", "notices.responder"} & names


@pytest.mark.parametrize("code", KINDS)
def test_ac1_the_seven_notice_kinds_are_registered(code: str) -> None:
    found = kind_of(code)
    assert found is not None
    assert found.code == code
