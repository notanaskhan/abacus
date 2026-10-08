"""SPEC-013 catalogue invariants."""

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
    }
