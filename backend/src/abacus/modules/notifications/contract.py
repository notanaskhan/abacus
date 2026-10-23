"""C16 v1, the notifications half (P-01-T01 stub; ADR P-36). The v2 list, its counts and the
per-kind preferences. Behind `notifications.v2`: off, the routes answer 404. The feed is live
since P-01-T06, the preferences since P-01-T12.

During the v1 to v2 sprint the v2 list is served beside v1 at `/v1/notifications/feed`; it takes
over `GET /v1/notifications` when the v1 consumer is gone (contract change log)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import NOTIFICATIONS_V2
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import OWN, AbacusRouter, AuthContext, current_member
from abacus.modules.notifications.service import (
    Preference,
    feed,
    my_preferences,
    set_my_preferences,
)

Member = Annotated[AuthContext, Depends(current_member)]
Category = Literal["approval", "mention", "client_activity", "run", "deadline", "system", "other"]
Tab = Literal["all", "approvals", "mentions", "client_activity"]
# Closed set (C16): a kind may offer only these on its row.
InlineAction = Literal["accept_document", "return_document", "open_sign_off"]
ActorKind = Literal["human", "agent", "system", "policy"]


class NotificationActorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[ActorKind, classified("internal")]
    user_id: Annotated[UUID | None, classified("internal")] = None


class ObjectRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class NotificationItemOut(BaseModel):
    """A row as the drawer shows it. Rows store identifiers and codes only; `facts` are
    resolved at read time and may hold client content, so they are Restricted and never logged."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, classified("internal")]
    category: Annotated[Category, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    read: Annotated[bool, classified("internal")]
    actor: Annotated[NotificationActorOut, classified("internal")]
    subject: Annotated[ObjectRefOut, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    facts: Annotated[dict[str, str | int | bool | None], classified("restricted")]
    inline_actions: Annotated[list[InlineAction], classified("internal")]
    pending: Annotated[bool, classified("internal")]


class NotificationCountsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    approvals: Annotated[int, classified("internal")]
    mentions: Annotated[int, classified("internal")]
    client_activity: Annotated[int, classified("internal")]


class NotificationFeedOut(BaseModel):
    """The P-36 list envelope plus the tab counts and the bell's unread count."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[NotificationItemOut], classified("internal")]
    next_cursor: Annotated[str | None, classified("internal")]
    counts: Annotated[NotificationCountsOut, classified("internal")]
    unread_count: Annotated[int, classified("internal")]


class NotificationPreferenceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    in_app: Annotated[bool, classified("internal")]
    email: Annotated[bool, classified("internal")]


class NotificationPreferencesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[NotificationPreferenceOut], classified("internal")]


class NotificationPreferencesIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: Annotated[list[NotificationPreferenceOut], classified("internal")]


async def _v2_on(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, NOTIFICATIONS_V2):
        raise NotFound("notifications.v2")


def _preferences_out(found: list[Preference]) -> NotificationPreferencesOut:
    return NotificationPreferencesOut(
        items=[
            NotificationPreferenceOut(kind=p.kind, in_app=p.in_app, email=p.email) for p in found
        ]
    )


feed_router = AbacusRouter(prefix="/v1/notifications", tags=["notifications"])
preferences_router = AbacusRouter(prefix="/v1/me", tags=["notifications"])


@feed_router.get("/feed", action=OWN, response_model=NotificationFeedOut)
async def notification_feed_route(
    ctx: Member,
    tab: Annotated[Tab, Query()] = "all",
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    days: Annotated[int, Query(ge=1, le=30)] = 30,
) -> NotificationFeedOut:
    """P-01-T06: live behind `notifications.v2` (off: 404)."""
    if not await flag_enabled(ctx.tenant, NOTIFICATIONS_V2):
        raise NotFound("notifications.v2")
    found = await feed(ctx, tab=tab, cursor=cursor, limit=limit, days=days)
    return NotificationFeedOut(
        items=[
            NotificationItemOut(
                id=i.id,
                kind=i.kind,
                category=i.category,  # type: ignore[arg-type]  # a stored category code
                created_at=i.created_at,
                read=i.read,
                actor=NotificationActorOut(
                    kind=i.actor_kind,  # type: ignore[arg-type]  # a stored actor kind
                    user_id=i.actor_user_id,
                ),
                subject=ObjectRefOut(type=i.subject_type, id=i.subject_id),
                engagement_id=i.engagement_id,
                facts=i.facts,
                inline_actions=list(i.inline_actions),
                pending=i.pending,
            )
            for i in found.items
        ],
        next_cursor=found.next_cursor,
        counts=NotificationCountsOut(
            approvals=found.approvals,
            mentions=found.mentions,
            client_activity=found.client_activity,
        ),
        unread_count=found.unread_count,
    )


@preferences_router.get(
    "/notification-preferences",
    action=OWN,
    response_model=NotificationPreferencesOut,
)
async def notification_preferences_route(ctx: Member) -> NotificationPreferencesOut:
    """P-01-T12: every registered kind with the caller's own choice, or its default."""
    await _v2_on(ctx)
    return _preferences_out(await my_preferences(ctx))


@preferences_router.put(
    "/notification-preferences",
    action=OWN,
    response_model=NotificationPreferencesOut,
)
async def set_notification_preferences_route(
    given: NotificationPreferencesIn, ctx: Member
) -> NotificationPreferencesOut:
    """P-01-T12: the caller's own choices (OWN); 422 `unknown_notification_kind` for a kind not
    registered or named twice. Email for a kind sends only while `notifications.email` is on."""
    await _v2_on(ctx)
    items = [Preference(i.kind, i.in_app, i.email) for i in given.items]
    return _preferences_out(await set_my_preferences(ctx, items))
