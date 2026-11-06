"""N-04-T23 (ADR-078), part 2: the response chain, written outside the implementing session:
sign-off staleness, the three refusals in order, readiness only after signatures and an accepted
confirmation, consumer idempotence, mark-sent validation, the alert days, and no Response sent
without signatures. Workflow replays are in tests/workflows (`notice-response-v1-*`)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.kernel.uow import OutboxEvent
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import response, sending
from abacus.modules.notices.response import Block
from abacus.modules.notices.response_workflow import alert_days
from abacus.modules.notices.sending import follow_up_on, readiness_of

HUMAN = Block("block:2", "human", "block:2", "The basis is on Form 8949.", False)
TEMPLATE = Block("block:1", "template", "block:1", "We disagree.", False)
POSITIONS = st.sampled_from(["agree", "partial", "disagree"])


@given(drafted=st.one_of(st.none(), POSITIONS))
def test_no_decided_position_always_refuses_first(drafted: str | None) -> None:
    assert response.blocked_code(None, drafted, [HUMAN]) == "decision_pending"


@given(position=POSITIONS, drafted=POSITIONS)
def test_a_draft_for_another_position_refuses_before_the_explanation(
    position: str, drafted: str
) -> None:
    found = response.blocked_code(position, drafted, [TEMPLATE])
    if position != drafted:
        assert found == "position_mismatch"


def test_only_a_person_explains_a_disagreement() -> None:
    assert response.blocked_code("disagree", "disagree", [TEMPLATE]) == "explanation_required"
    assert response.blocked_code("disagree", "disagree", [TEMPLATE, HUMAN]) is None
    assert response.blocked_code("agree", "agree", [TEMPLATE]) is None


@given(a=st.text(min_size=1, max_size=40), b=st.text(min_size=1, max_size=40))
def test_any_edit_moves_the_hash_an_old_sign_off_holds(a: str, b: str) -> None:
    first = response.content_hash([{"key": "block:1", "text": a}])
    second = response.content_hash([{"key": "block:1", "text": b}])
    assert (first == second) == (a == b)


@given(
    payment=st.one_of(
        st.none(),
        st.fixed_dictionaries({"required": st.booleans(), "confirmation_accepted": st.booleans()}),
    ),
    included=st.booleans(),
)
def test_no_response_is_ever_ready_unsigned(
    payment: Mapping[str, object] | None, included: bool
) -> None:
    enclosures = [{"included": included, "evidence_version_id": str(uuid4())}]
    assert readiness_of(False, payment, enclosures).ready is False


def test_a_required_payment_waits_for_the_accepted_confirmation() -> None:
    waiting = readiness_of(True, {"required": True, "confirmation_accepted": False}, [])
    assert waiting.ready is False
    assert "payment" in waiting.blocking
    assert readiness_of(True, {"required": True, "confirmation_accepted": True}, []).ready


async def test_mark_sent_refuses_before_ready_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def found(_ctx: object, _id: object) -> object:
        return SimpleNamespace(engagement_id=uuid4())

    async def not_ready(_ctx: object, _id: object) -> object:
        return readiness_of(False, None, [])

    monkeypatch.setattr(sending, "notice", found)
    monkeypatch.setattr(sending, "readiness", not_ready)
    with pytest.raises(sending.NotReady):
        await sending.mark_sent(
            cast(AuthContext, SimpleNamespace(tenant=None)),
            uuid4(),
            channel="mail",
            confirmation_no=None,
            sent_on=date(2026, 9, 17),
            follow_up_days=60,
        )


def _completed(source_kind: str) -> OutboxEvent:
    return OutboxEvent(
        event_id=uuid4(),
        tenant_id=uuid4(),
        event_type="envelope.completed",
        payload={"source_kind": source_kind, "envelope_id": str(uuid4())},
    )


async def test_another_sources_envelope_is_not_this_consumers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published: list[object] = []

    async def publish(*args: object, **_kw: object) -> None:
        published.append(args)

    monkeypatch.setattr(sending, "_publish_when_ready", publish)
    await sending.on_envelope_completed(_completed("engagement_letter"))
    assert published == []


def test_the_sixty_day_follow_up_lands_on_the_calendar_day() -> None:
    assert follow_up_on(date(2026, 9, 17), 60) == date(2026, 11, 16)


def test_a_cp3219a_gets_the_long_alert_ladder() -> None:
    assert alert_days("cp3219a") == (30, 14, 7, 2)
    assert alert_days("cp2000") == (7, 2)
