"""Notification routes (SPEC-013 §8): the caller's own only (route marker `OWN`, Q3)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.identity.api import OWN, AbacusRouter, AuthContext, current_member
from abacus.modules.notifications.service import my_notifications, read_all, read_one

router = AbacusRouter(prefix="/v1/notifications", tags=["notifications"])
Member = Annotated[AuthContext, Depends(current_member)]


class NotificationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    subject_type: Annotated[str, classified("internal")]
    subject_id: Annotated[UUID, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    read: Annotated[bool, classified("internal")]


class NotificationPageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[NotificationOut], classified("internal")]
    unread_count: Annotated[int, classified("internal")]


class ReadAllOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    marked: Annotated[int, classified("internal")]


@router.get("", action=OWN, response_model=NotificationPageOut)
async def list_notifications_route(
    ctx: Member,
    unread: Annotated[bool, Query()] = False,
    before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationPageOut:
    page = await my_notifications(ctx, unread_only=unread, before=before, limit=limit)
    return NotificationPageOut(
        items=[NotificationOut.model_validate(asdict(item)) for item in page.items],
        unread_count=page.unread_count,
    )


@router.post("/{notification_id}/read", action=OWN, response_model=NotificationPageOut)
async def read_notification_route(notification_id: UUID, ctx: Member) -> NotificationPageOut:
    await read_one(ctx, notification_id)
    page = await my_notifications(ctx, unread_only=False, before=None, limit=50)
    return NotificationPageOut(
        items=[NotificationOut.model_validate(asdict(item)) for item in page.items],
        unread_count=page.unread_count,
    )


@router.post("/read-all", action=OWN, response_model=ReadAllOut)
async def read_all_route(ctx: Member) -> ReadAllOut:
    return ReadAllOut(marked=await read_all(ctx))
