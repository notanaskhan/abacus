"""C16 v1, the notifications half (P-01-T01 stub; ADR P-36). The v2 list, its counts and the
per-kind preferences. Behind `notifications.v2`: off, the routes answer 404; on, 501
`not_implemented` until P-01-T06 (the catalogue v2) and P-01-T12 (preferences) land.

During the v1 to v2 sprint the v2 list is served beside v1 at `/v1/notifications/feed`; it takes
over `GET /v1/notifications` when the v1 consumer is gone (contract change log)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import NOTIFICATIONS_V2
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import OWN, AbacusRouter, AuthContext, current_member

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


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, NOTIFICATIONS_V2):
        raise NotFound("notifications.v2")
    raise NotImplementedYet


feed_router = AbacusRouter(prefix="/v1/notifications", tags=["notifications"])
preferences_router = AbacusRouter(prefix="/v1/me", tags=["notifications"])


@feed_router.get("/feed", action=OWN, response_model=NotificationFeedOut, errors=(501,))
async def notification_feed_route(
    ctx: Member,
    tab: Annotated[Tab, Query()] = "all",
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    days: Annotated[int, Query(ge=1, le=30)] = 30,
) -> NotificationFeedOut:
    await _stub(ctx)


@preferences_router.get(
    "/notification-preferences",
    action=OWN,
    response_model=NotificationPreferencesOut,
    errors=(501,),
)
async def notification_preferences_route(ctx: Member) -> NotificationPreferencesOut:
    await _stub(ctx)


@preferences_router.put(
    "/notification-preferences",
    action=OWN,
    response_model=NotificationPreferencesOut,
    errors=(501,),
)
async def set_notification_preferences_route(
    given: NotificationPreferencesIn, ctx: Member
) -> NotificationPreferencesOut:
    await _stub(ctx)
