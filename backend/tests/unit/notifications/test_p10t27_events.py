"""P-10-T27 (TASK-6517; SPEC-647 AC-T9; ADR-232 proposed; DEC-3117): the invalidation stream.

Row acceptance: "request_item.status_changed reaches engagement and work_item subscribers as
identifiers only, a firm admin gets metadata topics only, and a portal principal can subscribe
only to its own grant scope."
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest

import abacus.modules.notifications.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers
from abacus.kernel import realtime
from abacus.modules.identity.api import AuthContext
from abacus.modules.notifications import realtime as live

pytestmark = pytest.mark.asyncio


def test_a_request_item_status_change_names_both_topics_by_id() -> None:
    found = realtime.invalidation_of("request_item.status_changed")
    assert found is not None
    assert found.ref_type == "request_item"
    assert dict(found.topic_fields) == {"engagement": "engagement_id", "work_item": "work_item_id"}


async def test_unknown_kinds_and_other_users_are_refused() -> None:
    me = SimpleNamespace(user_id=uuid.uuid4(), client=False)
    assert await realtime.authorise_topic(me, f"user:{me.user_id}") == "content"
    assert await realtime.authorise_topic(me, f"user:{uuid.uuid4()}") is None
    assert await realtime.authorise_topic(me, "secrets:everything") is None
    assert await realtime.authorise_topic(me, "firm:home") == "content"


async def test_a_portal_principal_holds_only_portal_topics() -> None:
    client = cast(AuthContext, SimpleNamespace(user_id=uuid.uuid4(), client=True))  # portal person
    with pytest.raises(live.TopicRefused):
        await live._authorised(client, [f"engagement:{uuid.uuid4()}"])  # pyright: ignore[reportPrivateUsage]  # the rule under test


def test_topics_parse_sorted_and_bounded() -> None:
    raw = ",".join(f"run:{n}" for n in range(150)) + ", user:x ,,"
    parsed = live.parse_topics(raw)
    assert len(parsed) == 100 and parsed == sorted(parsed)


async def test_metadata_holders_get_only_notice_and_locked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.engagements import realtime_topics as et

    async def ref(_ctx: object, _e: uuid.UUID) -> object:
        from abacus.modules.identity.api import Resource

        return SimpleNamespace(
            resource=lambda: Resource(uuid.uuid4(), archived=False, engagement_id=_e)
        )

    async def nothing(*_a: object) -> list[str]:
        return []

    tenant = uuid.uuid4()
    admin = SimpleNamespace(user_id=uuid.uuid4(), tenant_id=tenant, client=False)
    staff = SimpleNamespace(user_id=uuid.uuid4(), tenant_id=tenant, client=False)

    async def admins(_t: uuid.UUID) -> list[uuid.UUID]:
        return [admin.user_id]  # identity's firm admins (S33 end pass: no role read here)

    monkeypatch.setattr("abacus.modules.engagements.api.get_ref", ref)
    monkeypatch.setattr(et, "allowed_actions", nothing)
    monkeypatch.setattr(et, "firm_admins", admins)
    assert await et.engagement_topic(admin, str(uuid.uuid4())) == "metadata"
    assert await et.engagement_topic(staff, str(uuid.uuid4())) is None


async def test_review_a_refused_seventh_stream_registers_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S33 security review: the slot is claimed before the stream is registered."""
    from abacus.kernel import realtime as rt

    async def allowed(_ctx: object, topics: list[str]) -> dict[str, str]:
        return dict.fromkeys(topics, "content")

    def full(*_a: object) -> None:
        raise rt.TooManyStreams(facts={"limit": rt.MAX_STREAMS_PER_USER})

    monkeypatch.setattr(live, "_authorised", allowed)
    monkeypatch.setattr(rt, "claim_slot", full)
    before = dict(live._STREAMS)  # pyright: ignore[reportPrivateUsage]  # the registry under test
    person = cast(AuthContext, SimpleNamespace(user_id=uuid.uuid4(), tenant_id=uuid.uuid4()))
    with pytest.raises(rt.TooManyStreams):
        await live.events_stream(person, ["user:x"], None)
    assert before == live._STREAMS  # pyright: ignore[reportPrivateUsage]  # nothing leaked


async def test_review_a_stream_never_grows_past_the_topic_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def allowed(_ctx: object, topics: list[str]) -> dict[str, str]:
        return dict.fromkeys(topics, "content")

    monkeypatch.setattr(live, "_authorised", allowed)
    user = uuid.uuid4()
    stream = uuid.uuid4()
    held = {f"run:{n}": "content" for n in range(live.MAX_TOPICS)}
    monkeypatch.setitem(live._STREAMS, stream, (user, held))  # pyright: ignore[reportPrivateUsage]  # the registry
    person = cast(AuthContext, SimpleNamespace(user_id=user))
    with pytest.raises(live.TopicRefused):
        await live.change_topics(person, stream, ["run:extra"], [])
    swapped = await live.change_topics(person, stream, ["run:extra"], ["run:0"])
    assert "run:extra" in swapped and len(swapped) == live.MAX_TOPICS
