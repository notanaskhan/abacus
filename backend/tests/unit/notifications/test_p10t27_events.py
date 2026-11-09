"""P-10-T27 (TASK-6517; SPEC-647 AC-T9; ADR-232 proposed; DEC-3117): the invalidation stream.

Row acceptance: "request_item.status_changed reaches engagement and work_item subscribers as
identifiers only, a firm admin gets metadata topics only, and a portal principal can subscribe
only to its own grant scope."
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

import abacus.modules.notifications.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers
from abacus.kernel import realtime
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
    client = SimpleNamespace(user_id=uuid.uuid4(), client=True)
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

        return SimpleNamespace(resource=lambda: Resource(uuid.uuid4(), engagement_id=_e))

    async def nothing(*_a: object) -> list[str]:
        return []

    monkeypatch.setattr("abacus.modules.engagements.api.get_ref", ref)
    monkeypatch.setattr(et, "allowed_actions", nothing)
    admin = SimpleNamespace(user_id=uuid.uuid4(), client=False, firm_role="firm_admin")
    staff = SimpleNamespace(user_id=uuid.uuid4(), client=False, firm_role="staff")
    assert await et.engagement_topic(admin, str(uuid.uuid4())) == "metadata"
    assert await et.engagement_topic(staff, str(uuid.uuid4())) is None
