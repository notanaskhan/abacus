"""T-02-T07 (TASK-2118; SPEC-502 AC-8): the return status machine refuses any move its table does
not hold, and a request may name only the two person events."""

from __future__ import annotations

import pytest

from abacus.kernel._statuses import ReturnStatus as S
from abacus.modules.tax import api as tax_api
from abacus.modules.tax.status import REQUESTABLE, actor_may


def test_ac8_the_happy_path_walks_the_blueprint_order() -> None:
    walk = [
        ("intake_opened", S.GATHERING),
        ("start_preparation", S.PREPARING),
        ("prepared", S.PREPARED),
        ("start_review", S.IN_REVIEW),
        ("final_approved", S.APPROVED),
        ("envelope_sent", S.AWAITING_SIGNATURE),
        ("transmission_recorded", S.FILED),
        ("ack_accepted", S.ACCEPTED),
    ]
    current = S.NOT_STARTED
    for event, expected in walk:
        current = tax_api.next_status(current, event)
        assert current is expected, event


@pytest.mark.parametrize(
    ("current", "event"),
    [
        (S.NOT_STARTED, "final_approved"),
        (S.PREPARING, "transmission_recorded"),
        (S.ACCEPTED, "start_review"),
        (S.IN_REVIEW, "ack_accepted"),
    ],
)
def test_ac8_a_move_the_table_does_not_hold_is_refused(current: S, event: str) -> None:
    with pytest.raises(tax_api.TransitionRefused) as raised:
        tax_api.next_status(current, event)
    assert raised.value.code == "transition_refused"


def test_ac8_a_request_names_only_the_two_person_events() -> None:
    assert {"start_preparation", "start_review"} == REQUESTABLE
    assert "final_approved" not in REQUESTABLE  # T-01's approval.py raises it


def test_ac8_every_status_in_the_table_is_a_registry_code() -> None:
    for (source, _event), target in tax_api.TRANSITIONS.items():
        assert source in S and target in S


@pytest.mark.parametrize(
    ("event", "kind", "allowed"),
    [
        ("start_review", "human", True),
        ("final_approved", "human", True),
        ("transmission_recorded", "system", True),
        ("final_approved", "system", False),
        ("start_review", "agent", False),
        ("final_approved", "agent", False),
        ("prepared", "support", False),
    ],
)
def test_review_s1_only_a_person_approves_and_the_agent_never_moves_a_return(
    event: str, kind: str, allowed: bool
) -> None:
    """End review S1: the agent and support never move a return, and the final approval is a
    person's alone; the status event records the actor's own kind."""
    assert actor_may(event, kind) is allowed
