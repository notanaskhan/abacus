"""SPEC-032 (TASK-062): comment rules that need no database."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid
from abacus.modules.engagements.api import EngagementRef
from abacus.modules.identity.api import AuthContext
from abacus.modules.notifications.catalogue import CATALOGUE, TEMPLATES
from abacus.modules.requests import comments
from abacus.modules.requests.comments import (
    CommentOutOfScope,
    EmptyComment,
    MentionNotAllowed,
    SharingUnavailable,
    candidates,
    clean_text,
)
from abacus.modules.requests.service import RequestItemRef

T, E, ITEM = uuid4(), uuid4(), uuid4()
PARTNER, ADMIN, CONTRIBUTOR, OTHER = uuid4(), uuid4(), uuid4(), uuid4()


def _ctx(user: UUID) -> AuthContext:
    return AuthContext(
        TenantContext(T, "human", str(user)), user, uuid4(), None, datetime.now(UTC)
    )


def _item(visible: bool = True, assignee: UUID | None = CONTRIBUTOR) -> RequestItemRef:
    return RequestItemRef(ITEM, E, "open", visible, assignee)


@pytest.fixture
def people(monkeypatch: pytest.MonkeyPatch) -> None:
    async def team_of(tenant_id: UUID, engagement_id: UUID) -> list[tuple[UUID, str]]:
        return [(PARTNER, "engagement_partner")]

    async def client_admins(tenant: TenantContext, engagement_id: UUID) -> list[UUID]:
        return [ADMIN]

    async def role_of(tenant: TenantContext, engagement_id: UUID, user: UUID) -> str | None:
        return {CONTRIBUTOR: "client_contributor", ADMIN: "client_admin"}.get(
            user, "engagement_partner"
        )

    monkeypatch.setattr(comments, "team_of", team_of)
    monkeypatch.setattr(comments, "client_admins", client_admins)
    monkeypatch.setattr(comments, "engagement_role_of", role_of)


def test_ac9_text_is_plain_and_bounded() -> None:
    assert clean_text("  a\u0000b\nc\t ", 10) == "ab\nc"
    with pytest.raises(EmptyComment):
        clean_text(" ​\u0007 ", 10)
    with pytest.raises(DomainInvalid):
        clean_text("x" * 11, 10)


@pytest.mark.usefixtures("people")
async def test_ac5_internal_notes_mention_the_firm_only() -> None:
    assert await candidates(_ctx(PARTNER), E, _item(), "internal") == {PARTNER: "firm"}


@pytest.mark.usefixtures("people")
async def test_ac5_shared_comments_add_the_items_client_readers() -> None:
    found = await candidates(_ctx(PARTNER), E, _item(), "shared")
    assert found == {PARTNER: "firm", ADMIN: "client", CONTRIBUTOR: "client"}
    hidden = await candidates(_ctx(PARTNER), E, _item(visible=False), "shared")
    assert hidden == {PARTNER: "firm"}


@pytest.fixture
def thread_as(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    def use(role: str) -> None:
        async def _thread(*args: object) -> tuple[object, RequestItemRef, str]:
            return object(), _item(), role

        async def authorise(*args: object) -> None:
            return None

        monkeypatch.setattr(comments, "_thread", _thread)
        monkeypatch.setattr(comments, "authorise", authorise)

        def resource(ref: object, item: object) -> None:
            return None

        monkeypatch.setattr(comments, "_resource", resource)

    return use


@pytest.mark.usefixtures("people")
async def test_ac7_sharing_fails_closed_without_a_scope_check(
    monkeypatch: pytest.MonkeyPatch,
    thread_as: Callable[[str], None],
) -> None:
    thread_as("senior")
    monkeypatch.setattr(comments, "_scope_check", None)
    with pytest.raises(SharingUnavailable):
        await comments.post_comment(_ctx(PARTNER), E, ITEM, None, text="hello", share=True)


@pytest.mark.usefixtures("people")
async def test_ac7_a_violation_blocks_a_shared_firm_comment(
    monkeypatch: pytest.MonkeyPatch,
    thread_as: Callable[[str], None],
) -> None:
    thread_as("senior")

    async def check(*args: object) -> list[str]:
        return ["client"]

    monkeypatch.setattr(comments, "_scope_check", check)
    with pytest.raises(CommentOutOfScope):
        await comments.post_comment(_ctx(PARTNER), E, ITEM, None, text="Contoso too", share=True)


@pytest.mark.usefixtures("people")
async def test_ac5_mentioning_someone_who_cant_read_it_is_refused(
    thread_as: Callable[[str], None],
) -> None:
    thread_as("senior")
    with pytest.raises(MentionNotAllowed):
        await comments.post_comment(_ctx(PARTNER), E, ITEM, None, text="hi", mentions=[ADMIN])
    with pytest.raises(MentionNotAllowed):
        await comments.post_comment(_ctx(PARTNER), E, ITEM, None, text="hi", mentions=[OTHER])


async def test_ac5_mentions_notify_each_person_once() -> None:
    kind = CATALOGUE["comment.mentioned"]
    payload: dict[str, object] = {"mentioned_user_ids": [str(ADMIN), str(ADMIN), str(PARTNER)]}
    assert await kind.recipients(T, payload) == sorted({ADMIN, PARTNER})
    assert kind.subject_type == "request_item"
    assert "{engagement}" in TEMPLATES["comment.mentioned"]


async def test_ac7_a_failing_checker_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.communications import scope

    async def broken(*args: object) -> list[object]:
        raise RuntimeError("down")

    monkeypatch.setattr(scope, "check_scope", broken)
    ref = cast(EngagementRef, object())  # never read: the check fails first
    assert await scope.comment_scope_kinds(_ctx(PARTNER), ref, "x") == ["checker_error"]
