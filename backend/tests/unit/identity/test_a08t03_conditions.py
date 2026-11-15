"""A-08-T03 (TASK-8045; SPEC-657 AC-0.3, AC-3.3, AC-7.3; DEC-5030): the three A-08 conditions,
driven through the pure `conditions_hold`, and the matrix rows that carry them."""

from __future__ import annotations

from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import RULES

_DECIDE = RULES["sample_expansion.decide"]
_RESPOND = RULES["confirmation.respond"]
_VIEW = RULES["confirmation.respond_view"]


def test_ac3_3_only_the_named_approver_who_did_not_request_decides() -> None:
    assert _DECIDE.is_named_approver and _DECIDE.not_preparer_of_target
    ok = ConditionFacts(named_approver=True, preparer=False)
    assert conditions_hold(_DECIDE, ok, person=True)
    assert not conditions_hold(
        _DECIDE, ConditionFacts(named_approver=False, preparer=False), person=True
    )
    assert not conditions_hold(
        _DECIDE, ConditionFacts(named_approver=True, preparer=True), person=True
    )
    assert not conditions_hold(_DECIDE, ConditionFacts(preparer=False), person=True)  # no facts
    assert not conditions_hold(_DECIDE, ok, person=False)  # an agent or a system run never


def test_ac7_3_a_response_needs_the_link_scope_and_a_verified_email() -> None:
    both = ConditionFacts(link_scope=True, email_verified=True)
    assert conditions_hold(_RESPOND, both, person=False)
    assert not conditions_hold(_RESPOND, ConditionFacts(link_scope=True), person=False)
    assert not conditions_hold(_RESPOND, ConditionFacts(email_verified=True), person=False)
    assert not conditions_hold(_RESPOND, ConditionFacts(), person=False)
    # Viewing needs only the scope.
    assert conditions_hold(_VIEW, ConditionFacts(link_scope=True), person=False)


def test_ac0_3_the_public_family_is_the_link_principals_alone() -> None:
    for action in (
        "confirmation.respond_view",
        "confirmation.respond_verify",
        "confirmation.respond",
    ):
        allowed = {role for role, d in RULES[action].decisions.items() if d != "deny"}
        assert allowed == {"link_principal"}, action


def test_ac0_3_no_client_or_link_principal_reaches_a_firm_confirmation_route() -> None:
    firm = [
        a
        for a in RULES
        if a.startswith("confirmation.") and not a.startswith("confirmation.respond")
    ]
    assert len(firm) == 11
    for action in firm:
        for role in (
            "client_admin",
            "client_contributor",
            "third_party",
            "link_principal",
            "agent",
        ):
            assert RULES[action].decisions.get(role, "deny") in ("deny", "task_scope"), (
                action,
                role,
            )
