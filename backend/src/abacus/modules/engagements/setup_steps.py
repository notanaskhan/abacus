"""SPEC-025 AC-10 (TASK-046 D1): the setup page's checklist and narrative summary, computed from
facts the setup view already read. Pure: no reads, no model; the same words wherever they show.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal

StepState = Literal["done", "waiting", "blocked", "warning", "not_needed"]
StepKey = Literal[
    "client_and_period",
    "team",
    "request_list",
    "acceptance",
    "independence_conclusion",
    "independence",
    "letter",
    "client_contacts",
]

ROLE_LABEL: Final = {
    "engagement_partner": "engagement partner",
    "manager": "manager",
    "senior": "senior",
    "staff": "staff",
    "reviewer": "reviewer",
}
_KIND_LABEL: Final = {"new_client": "new client", "continuance": "continuance"}
# The gate's plain words (the web's `errorMessage` says the same for a refusal elsewhere).
_GATE_REASON: Final = {
    "acceptance_missing": "Client invitations open once {partner} records acceptance.",
    "acceptance_declined": "The engagement was declined, so client data stays closed.",
    "independence_conclusion_missing": (
        "Client invitations open once {partner} records their independence conclusion."
    ),
    "letter_missing": "Client invitations open once the engagement letter is recorded.",
}


@dataclass(frozen=True)
class Member:
    name: str
    role: str


@dataclass(frozen=True)
class Confirmation:
    name: str
    status: str  # requested | confirmed | declined


@dataclass(frozen=True)
class SetupFacts:
    engagement_name: str
    client_name: str
    kind: str  # the acceptance's, or what it would be pre-filled as
    period_start: date
    period_end: date
    team: Sequence[Member]
    firm_admins: Sequence[str]
    methodology_applied: bool
    acceptance_decision: str | None  # accepted | declined | None (not recorded)
    acceptance_at: datetime | None
    concluded: bool
    letter_status: str | None
    letter_required: bool
    confirmations: Sequence[Confirmation]
    contacts_joined: int
    contacts_invited: int
    blocked: str | None


@dataclass(frozen=True)
class Step:
    key: StepKey
    label: str
    state: StepState
    detail: str | None = None
    next: str | None = None  # who acts next
    reason: str | None = None  # on blocked and warning only


def _names(team: Sequence[Member], roles: frozenset[str]) -> list[str]:
    return [m.name or "Someone" for m in team if m.role in roles]


def has_partner(team: Sequence[Member]) -> bool:
    """Who's named on the checklist, not a permission (those go through `authorise`)."""
    return bool(_names(team, frozenset({"engagement_partner"})))


def _who(names: Sequence[str], label: str) -> str:
    if not names:
        return f"the {label}"
    return f"{' or '.join(names)} ({label})"


def _partner_words(facts: SetupFacts) -> str:
    """'Dana Lee', or 'the engagement partner' when there's none (or several)."""
    partners = _names(facts.team, frozenset({"engagement_partner"}))
    return partners[0] if len(partners) == 1 else "the engagement partner"


def steps(facts: SetupFacts) -> list[Step]:
    partners = _names(facts.team, frozenset({"engagement_partner"}))
    partner = _who(partners, "engagement partner")
    leads = _who(
        _names(facts.team, frozenset({"engagement_partner", "manager"})), "partner or manager"
    )
    found: list[Step] = [
        Step(
            "client_and_period",
            "Client and period",
            "done",
            f"{facts.client_name} · {facts.period_start.isoformat()} to "
            f"{facts.period_end.isoformat()}",
        )
    ]
    found.append(
        Step("team", "Team", "done", f"{len(facts.team)} on the team")
        if partners
        else Step(
            "team",
            "Team",
            "waiting",
            "No engagement partner yet",
            _who(facts.firm_admins, "firm administrator"),
        )
    )
    found.append(
        Step("request_list", "Request list", "done", "Template applied")
        if facts.methodology_applied
        else Step("request_list", "Request list", "waiting", "No template applied yet", leads)
    )
    found.append(_acceptance(facts, partner))
    found.append(
        Step("independence_conclusion", "Partner's independence conclusion", "done", "Concluded")
        if facts.concluded
        else Step(
            "independence_conclusion",
            "Partner's independence conclusion",
            "waiting",
            "Not recorded yet",
            partner,
        )
    )
    found.append(_independence(facts))
    found.append(_letter(facts, leads))
    found.append(_contacts(facts, leads))
    return found


def _acceptance(facts: SetupFacts, partner: str) -> Step:
    label = "Continuance" if facts.kind == "continuance" else "Acceptance"
    if facts.acceptance_decision == "accepted":
        return Step("acceptance", label, "done", "Accepted")
    if facts.acceptance_decision == "declined":
        on = f" on {facts.acceptance_at.date().isoformat()}" if facts.acceptance_at else ""
        return Step(
            "acceptance",
            label,
            "blocked",
            f"Declined{on}",
            partner,
            "Declined, so client data stays closed. Record it again if that changes.",
        )
    return Step("acceptance", label, "waiting", "Not recorded yet", partner)


def _independence(facts: SetupFacts) -> Step:
    total = len(facts.confirmations)
    confirmed = sum(1 for c in facts.confirmations if c.status == "confirmed")
    detail = f"{confirmed} of {total} confirmed"
    declined = [c.name or "Someone" for c in facts.confirmations if c.status == "declined"]
    waiting = [c.name or "Someone" for c in facts.confirmations if c.status == "requested"]
    label = "Team independence"
    if declined:
        return Step(
            "independence",
            label,
            "warning",
            detail,
            ", ".join(waiting) or None,
            f"{', '.join(declined)} declined. They can't see client data; the partner decides.",
        )
    if waiting:
        return Step("independence", label, "waiting", detail, ", ".join(waiting))
    return Step("independence", label, "done", detail)


def _letter(facts: SetupFacts, leads: str) -> Step:
    status = facts.letter_status
    if status == "signed":
        return Step("letter", "Engagement letter", "done", "Signed")
    if status == "not_required_this_year":
        return Step("letter", "Engagement letter", "not_needed", "Not required this year")
    detail = "Sent to the client" if status == "sent" else "Not recorded yet"
    if facts.letter_required:
        return Step(
            "letter",
            "Engagement letter",
            "blocked",
            detail,
            leads,
            "Your firm requires the signed letter before client data.",
        )
    return Step(
        "letter",
        "Engagement letter",
        "warning",
        detail,
        leads,
        "Preferably signed before work starts.",
    )


def _contacts(facts: SetupFacts, leads: str) -> Step:
    label = "Client contacts"
    detail = f"{facts.contacts_joined} joined, {facts.contacts_invited} invited"
    if facts.blocked is not None:
        reason = _GATE_REASON.get(facts.blocked, _GATE_REASON["acceptance_missing"])
        return Step(
            "client_contacts",
            label,
            "blocked",
            detail,
            None,
            reason.format(partner=_partner_words(facts)),
        )
    if facts.contacts_joined:
        return Step("client_contacts", label, "done", detail)
    return Step("client_contacts", label, "waiting", detail, leads)


def summary(facts: SetupFacts) -> str:
    title = f"{facts.client_name} {facts.engagement_name}"
    kind = _KIND_LABEL.get(facts.kind)
    head = f"{title} ({kind})" if kind else title
    confirmed = sum(1 for c in facts.confirmations if c.status == "confirmed")
    tally = f"{confirmed} of {len(facts.confirmations)} have confirmed independence."
    if facts.blocked is None:
        waiting = [c.name or "Someone" for c in facts.confirmations if c.status != "confirmed"]
        if waiting:
            verb = "hasn't" if len(waiting) == 1 else "haven't"
            tally = f"{tally[:-1]}; {', '.join(waiting)} {verb} yet."
        return f"{head} is open for client data. {tally}"
    return f"{head}: {_waiting_words(facts)} {tally}"


def _waiting_words(facts: SetupFacts) -> str:
    partner = _partner_words(facts)
    if not _names(facts.team, frozenset({"engagement_partner"})):
        return "waiting for an engagement partner."
    if facts.blocked == "acceptance_declined":
        return "declined, so client data stays closed."
    if facts.blocked == "independence_conclusion_missing":
        return f"waiting for {partner} to record their independence conclusion."
    if facts.blocked == "letter_missing":
        return "waiting for the engagement letter, which your firm requires."
    verb = "continuance" if facts.kind == "continuance" else "acceptance"
    return f"waiting for {partner} to record {verb}."
