"""SPEC-013 catalogue invariants."""

import uuid

import pytest

from abacus.modules.notifications.api import CATALOGUE, SUBSCRIPTIONS, TEMPLATES
from abacus.modules.notifications.email import SENTENCES


def test_ac7_every_kind_has_a_template() -> None:
    assert set(TEMPLATES) == set(CATALOGUE)


def test_ac7_each_event_emails_its_own_sentence() -> None:
    """ED-131: two events stored under one kind (`mention`) keep their own email sentence."""
    assert len(SENTENCES) == len(CATALOGUE)
    for event, entry in CATALOGUE.items():
        assert SENTENCES[(entry.kind, entry.subject_type)] == TEMPLATES[event], event
    assert SENTENCES[("mention", "request_item")].startswith("You were mentioned in a comment")


def test_ac1_every_catalogued_event_is_subscribed() -> None:
    assert set(SUBSCRIPTIONS) == set(CATALOGUE)


def test_ac1_the_catalogue_is_the_approved_kinds() -> None:
    assert set(CATALOGUE) == {
        "support_session.requested",
        "support_session.emergency_approved",
        "budget.soft_crossed",
        "budget.anomaly",
        "engagement.member_self_joined",
        "review.assigned",
        "engagement_member.added",  # SPEC-017 Q4
        "evidence.uploaded",  # SPEC-020: a client uploaded a file
        "connection.created",  # SPEC-020 (TASK-036 D5)
        "connection.revoked",
        "independence.requested",  # SPEC-025 (TASK-044)
        "reminders.drafted",  # SPEC-027 (TASK-051)
        "follow_up.drafted",  # P-06-T14: the same under its C16 code, follow_up_drafted
        "agent.digest",
        "comment.mentioned",  # SPEC-032 (TASK-062)
        "materiality.proposed",  # SPEC-305 (TASK-306)
        "risk.approval_requested",
        "finding.severity_proposed",
        "legal_hold.placed",  # Q-02-T29 (C16 `legal_hold_placed`)
        "incident.recorded",  # Q-02-T33 (C16 `incident_recorded`)
        "incident.propagated",  # Q-02-T33 (C16 `incident_from_accrued`)
        "wall.created",  # G-01-T09 (C16 `wall_approval_requested`, to the named partner)
        "wall.approved",  # G-01-T09 (C16 `wall_approved`, to the wall's creator)
        "portal.drop_unsorted",  # R-01-T09 (C16 `portal_drop_unsorted`)
        "follow_up.limit_reached",  # R-01-T24 (C16 `follow_up_limit_reached`, to the leads)
        "sending_domain.verified",  # R-01-T27 (R-01 §4.8, to the firm and security admins)
        "sending_domain.failed",  # R-01-T27 (R-01 §4.8, after 72 hours unverified)
        "membership.access_ending",  # G-01-T13 (C16 `seasonal_access_ending`, to firm admins)
        "third_party.uploaded",  # R-01-T13 (C16 `third_party_uploaded`, to the request owner)
        "sign_off.went_stale",  # P-04-T19 (C16 `sign_off_stale`, to the signer)
        "review_note.raised",  # P-04-T21 (C16 `review_note_raised`, to the assignee)
        "decision_card.raised",  # P-04-T23 (C16 `decision_assigned`, to the reserved person)
        "decision_card.notify_requested",  # P-04-T23 (C16 `mention`, SHL-11 b Notify)
        "proposal.routed",  # P-04-T26 (C16 `proposal_routed`, to the named approver)
        "sign_off.requested",  # P-04-T26 (`sign_off_requested`, to the people named)
        "issue.assigned",  # P-04-T26 (`issue_assigned`, to the assignee; P-04-T30 emits it)
        "checkpoint.created",  # P-04-T26 (`import_pending_approval`, an import's reviewers)
        "acceptance.sent_to_partner",  # P-07-T47 (C16 `acceptance_awaiting_partner`, to the EP)
        "acceptance.review_requested",  # P-07-T47 (`risk_partner_review_requested`)
        "independence.reminded",  # P-07-T47 (`independence_reminder`, to the member)
        "human_gate.reassigned",  # I-01-T07 (`gate_reassigned`, to the new person)
        "methodology.review_requested",  # K-01-T06 (`methodology_review_requested`)
        "independence.conclusion_due",  # P-07-T47 (`independence_conclusion_due`, to the EP)
        "team.change_proposed",  # P-07-T47 (`team_change_awaiting_approval`, to the EP)
        "engagement_export.ready",  # A-01-T22 (C16 `export_ready`, to the requester)
        "engagement_export.failed",  # A-01-T22 (C16 `export_failed`, to the requester)
        "audit_export.ready",  # G-02-T17 (C16 `audit_export_ready`, to the requester)
        "incident.decision_requested",  # G-02-T18 (to the named second decider)
        "incident.deadline_approaching",  # G-02-T18 (days 20, 25, 29: the QI and partners)
        "firm_export.requested",  # Q-02-T43 (C16 `firm_export_approval_requested`, the approver)
        "firm_export.ready",  # Q-02-T43 (C16 `firm_export_ready`, requester and approver)
        "connection.needs_reauth",  # A-02-T25 (C16 `connection_needs_reauth`, admins and leads)
        "connection.reauth_due",  # A-02-T25 (`connection_reauth_due`, 7 days ahead)
        "ai_policy.publish_requested",  # G-02-T24 (`ai_policy_approval_requested`, the approver)
    }


async def test_task307_the_partner_is_not_told_of_their_own_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.notifications import catalogue

    partner, other = uuid.uuid4(), uuid.uuid4()

    async def partners(*_: object) -> list[uuid.UUID]:
        return [partner, other]

    monkeypatch.setattr(catalogue, "engagement_partners", partners)
    payload: dict[str, object] = {"engagement_id": str(uuid.uuid4()), "by_user": str(partner)}
    assert await catalogue.CATALOGUE["materiality.proposed"].recipients(uuid.uuid4(), payload) == [
        other
    ]


async def test_q02t29_a_hold_tells_its_list_and_the_partners_but_no_client_or_walled_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.identity.api import MemberFacts
    from abacus.modules.notifications import catalogue

    placer, listed, partner, portal, walled = (uuid.uuid4() for _ in range(5))
    client = uuid.uuid4()

    async def partners(*_: object) -> list[uuid.UUID]:
        return [partner, walled, placer]

    async def facts(_tenant: object, user: uuid.UUID) -> MemberFacts | None:
        return MemberFacts(None, False, frozenset(), client=user == portal)

    async def walls(
        _tenant: object, user: uuid.UUID, clients: list[uuid.UUID]
    ) -> frozenset[uuid.UUID]:
        # G-01-T09: walls and offshore through `hidden_clients` (walled_from missed offshore).
        return frozenset(clients) & {client} if user == walled else frozenset()

    monkeypatch.setattr(catalogue, "engagement_partners", partners)
    monkeypatch.setattr(catalogue, "member_facts", facts)
    monkeypatch.setattr(catalogue, "hidden_clients", walls)
    payload: dict[str, object] = {
        "hold_id": str(uuid.uuid4()),
        "client_id": str(client),
        "engagement_ids": [str(uuid.uuid4())],
        "notify_user_ids": [str(listed), str(portal)],
        "by_user": str(placer),
    }
    found = await catalogue.CATALOGUE["legal_hold.placed"].recipients(uuid.uuid4(), payload)
    assert found == sorted([listed, partner])
    assert catalogue.CATALOGUE["legal_hold.placed"].kind == "legal_hold_placed"


async def test_q02t33_an_incident_tells_the_qi_and_partners_and_an_accrued_one_the_qi_and_admins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.notifications import catalogue

    qi, partner, admin = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def qis(*_: object) -> list[uuid.UUID]:
        return [qi]

    async def partners(*_: object) -> list[uuid.UUID]:
        return [partner]

    async def admins(*_: object) -> list[uuid.UUID]:
        return [admin]

    monkeypatch.setattr(catalogue, "security_admins", qis)
    monkeypatch.setattr(catalogue, "partner_members", partners)
    monkeypatch.setattr(catalogue, "firm_admins", admins)
    recorded = catalogue.CATALOGUE["incident.recorded"]
    assert recorded.kind == "incident_recorded" and recorded.engagement_key is None
    payload: dict[str, object] = {"incident_id": str(uuid.uuid4()), "by_user": str(qi)}
    assert await recorded.recipients(uuid.uuid4(), payload) == [partner]
    accrued = catalogue.CATALOGUE["incident.propagated"]
    assert accrued.kind == "incident_from_accrued"
    assert await accrued.recipients(uuid.uuid4(), {"incident_id": str(uuid.uuid4())}) == sorted(
        [qi, admin]
    )
