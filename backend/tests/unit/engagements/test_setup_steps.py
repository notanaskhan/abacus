"""SPEC-025 AC-10 (TASK-046): the setup page's checklist and summary, from facts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from abacus.modules.engagements.setup_steps import (
    Confirmation,
    Member,
    SetupFacts,
    Step,
    steps,
    summary,
)

NEW = SetupFacts(
    engagement_name="FY2026 audit",
    client_name="Northwind",
    kind="continuance",
    period_start=date(2026, 1, 1),
    period_end=date(2026, 12, 31),
    team=[Member("Dana Lee", "engagement_partner"), Member("Sam Patel", "staff")],
    firm_admins=[],
    methodology_applied=False,
    acceptance_decision=None,
    acceptance_at=None,
    concluded=False,
    letter_status=None,
    letter_required=False,
    confirmations=[Confirmation("Dana Lee", "requested"), Confirmation("Sam Patel", "requested")],
    contacts_joined=0,
    contacts_invited=0,
    blocked="acceptance_missing",
)
OPEN = replace(
    NEW,
    methodology_applied=True,
    acceptance_decision="accepted",
    concluded=True,
    confirmations=[Confirmation("Dana Lee", "confirmed"), Confirmation("Sam Patel", "requested")],
    blocked=None,
)


def _by_key(facts: SetupFacts) -> dict[str, Step]:
    return {s.key: s for s in steps(facts)}


def test_ac10_the_checklist_has_the_specs_eight_steps_in_order() -> None:
    assert [s.key for s in steps(NEW)] == [
        "client_and_period",
        "team",
        "request_list",
        "acceptance",
        "independence_conclusion",
        "independence",
        "letter",
        "client_contacts",
    ]


def test_ac10_a_new_engagement_waits_on_the_partner_and_says_why_contacts_are_blocked() -> None:
    found = _by_key(NEW)
    assert found["acceptance"].label == "Continuance"
    assert found["acceptance"].state == "waiting"
    assert found["acceptance"].next == "Dana Lee (engagement partner)"
    assert found["independence"].detail == "0 of 2 confirmed"
    assert found["independence"].next == "Dana Lee, Sam Patel"
    contacts = found["client_contacts"]
    assert contacts.state == "blocked"
    assert contacts.reason == "Client invitations open once Dana Lee records acceptance."
    assert summary(NEW) == (
        "Northwind FY2026 audit (continuance): waiting for Dana Lee to record continuance. "
        "0 of 2 have confirmed independence."
    )


def test_ac10_every_blocked_or_warning_step_has_a_reason() -> None:
    declined = replace(
        NEW,
        acceptance_decision="declined",
        acceptance_at=datetime(2026, 10, 3, tzinfo=UTC),
        letter_required=True,
        confirmations=[Confirmation("Sam Patel", "declined")],
        blocked="acceptance_declined",
    )
    for facts in (NEW, OPEN, declined):
        for step in steps(facts):
            assert (step.reason is not None) == (step.state in ("blocked", "warning")), step


def test_ac10_accepted_without_a_conclusion_waits_on_the_conclusion() -> None:
    facts = replace(NEW, acceptance_decision="accepted", blocked="independence_conclusion_missing")
    found = _by_key(facts)
    assert found["acceptance"].state == "done"
    assert found["independence_conclusion"].state == "waiting"
    assert found["client_contacts"].reason == (
        "Client invitations open once Dana Lee records their independence conclusion."
    )
    assert "waiting for Dana Lee to record their independence conclusion." in summary(facts)


def test_ac10_a_declined_engagement_is_blocked_with_its_date() -> None:
    facts = replace(
        NEW,
        acceptance_decision="declined",
        acceptance_at=datetime(2026, 10, 3, tzinfo=UTC),
        blocked="acceptance_declined",
    )
    step = _by_key(facts)["acceptance"]
    assert (step.state, step.detail) == ("blocked", "Declined on 2026-10-03")
    assert "declined, so client data stays closed." in summary(facts)


def test_ac10_the_letter_warns_unless_the_firm_requires_it() -> None:
    assert _by_key(OPEN)["letter"].state == "warning"
    assert _by_key(OPEN)["letter"].reason == "Preferably signed before work starts."
    required = replace(NEW, letter_required=True)
    assert _by_key(required)["letter"].state == "blocked"
    assert _by_key(replace(OPEN, letter_status="signed"))["letter"].state == "done"
    skipped = replace(OPEN, letter_status="not_required_this_year")
    assert _by_key(skipped)["letter"].state == "not_needed"


def test_ac10_a_decline_is_a_warning_naming_who() -> None:
    facts = replace(OPEN, confirmations=[Confirmation("Sam Patel", "declined")])
    step = _by_key(facts)["independence"]
    assert step.state == "warning"
    assert step.reason is not None and step.reason.startswith("Sam Patel declined.")


def test_ac10_no_partner_points_at_the_firm_administrators() -> None:
    facts = replace(NEW, team=[Member("Sam Patel", "staff")], firm_admins=["Ada Admin"])
    step = _by_key(facts)["team"]
    assert (step.state, step.next) == ("waiting", "Ada Admin (firm administrator)")
    assert "waiting for an engagement partner." in summary(facts)


def test_ac10_an_open_engagement_says_so_and_who_still_has_to_confirm() -> None:
    found = _by_key(OPEN)
    assert found["client_contacts"].state == "waiting"
    assert found["request_list"].state == "done"
    assert summary(OPEN) == (
        "Northwind FY2026 audit (continuance) is open for client data. "
        "1 of 2 have confirmed independence; Sam Patel hasn't yet."
    )
    joined = replace(OPEN, contacts_joined=1)
    assert _by_key(joined)["client_contacts"].state == "done"


def test_ac10_a_new_client_is_called_acceptance() -> None:
    facts = replace(NEW, kind="new_client")
    assert _by_key(facts)["acceptance"].label == "Acceptance"
    assert "(new client): waiting for Dana Lee to record acceptance." in summary(facts)
