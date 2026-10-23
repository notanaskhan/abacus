"""SPEC-013 catalogue invariants."""

import uuid

import pytest

from abacus.modules.notifications.api import CATALOGUE, SUBSCRIPTIONS, TEMPLATES


def test_ac7_every_kind_has_a_template() -> None:
    assert set(TEMPLATES) == set(CATALOGUE)


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
