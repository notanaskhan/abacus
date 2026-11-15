"""A-08-T01 (TASK-8043; A-08 §4.9, DF-05, DF-31; SPEC-657 AC-0.2): the fieldwork status rows, read
from the generated registry."""

from __future__ import annotations

from abacus.kernel import _statuses as s


def test_ac0_2_confirmation_statuses_follow_aud14() -> None:
    assert [m.value for m in s.ConfirmationStatus] == [
        "draft",
        "authorization_requested",
        "sent",
        "responded",
        "exception",
        "alternative_procedures",
        "closed",
    ]


def test_ac0_2_the_other_fieldwork_objects_are_generated() -> None:
    assert {m.value for m in s.LinkPrincipalStatus} == {
        "issued",
        "opened",
        "locked",
        "consumed",
        "expired",
        "revoked",
    }
    assert {m.value for m in s.JeTestStatus} == {"draft", "scoring", "scored", "failed"}
    assert {m.value for m in s.JeCriterionStatus} == {"available", "not_available"}
    assert {m.value for m in s.SampleExpansionStatus} == {
        "pending_approval",
        "approved",
        "rejected",
        "withdrawn",
    }
    assert {m.value for m in s.AnalyticsSetStatus} == {
        "computing",
        "current",
        "out_of_date",
        "superseded",
    }
    assert [m.value for m in s.AnalyticsLineStatus] == [
        "within",
        "unexplained",
        "explained",
        "accepted",
    ]


def test_the_agent_never_has_a_pass_or_exception_word_of_its_own() -> None:
    # I-AGENT-NEVER: the agent's view words are Agent-tested and Needs human; "Exception" is a
    # person's mark, so no result word starts with "agent_" except the outlined tick.
    agent_words = {m.value for m in s.FieldworkTestResultStatus if m.value.startswith("agent")}
    assert agent_words == {"agent_tested"}
