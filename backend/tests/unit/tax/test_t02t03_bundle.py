"""T-02-T03 (TASK-2114; SPEC-502 AC-1, AC-2): T-02's rows of the S16 protected bundle."""

from __future__ import annotations

import pytest

from abacus.kernel import _flags
from abacus.modules.identity.authz.matrix import RULES

FIRM_WRITES = (
    "tax_return.assign",
    "tax_return.status_change",
    "k1_package.share_internal",
    "k1_package.release",
    "k1_package.resend",
    "k1_recipient.review_details",
    "questionnaire_template.import",
    "questionnaire_template.publish",
    "questionnaire.create",
    "questionnaire.ask",
    "evidence.resolve_duplicate",
)
PORTAL = (
    "portal_questionnaire.read",
    "portal_questionnaire.answer",
    "portal_questionnaire.complete",
    "portal_questionnaire.submit",
    "portal_k1.read",
    "portal_k1.download",
    "portal_k1.update_details",
)


@pytest.mark.parametrize("action", FIRM_WRITES)
def test_ac1_firm_writes_deny_the_agent_the_system_and_clients(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor", "third_party"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)


@pytest.mark.parametrize("action", PORTAL)
def test_ac1_portal_rows_are_client_people_in_scope_never_the_agent(action: str) -> None:
    rule = RULES[action]
    assert rule.scope_only
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("client_admin") == "allow"


def test_ac1_release_and_template_publish_need_a_fresh_second_factor() -> None:
    assert RULES["k1_package.release"].mfa_recent
    assert RULES["questionnaire_template.publish"].mfa_recent


def test_ac2_the_four_flags_default_off() -> None:
    for flag in (
        _flags.TAX_RETURNS_V1,
        _flags.TAX_K1_RELEASE,
        _flags.QUESTIONNAIRES_V1,
        _flags.EVIDENCE_DUPLICATE_REVIEW,
    ):
        assert flag.default == "false"
