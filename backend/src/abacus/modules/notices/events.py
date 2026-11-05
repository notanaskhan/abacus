"""Notice events (N-04-T16; N-04 §4.7): identifiers, counts and dates only, no amounts (DEC-61)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class NoticeRespondBySoon(DomainEvent):
    event_type: ClassVar[str] = "notice.respond_by_soon"

    work_item_id: Annotated[UUID, classified("internal")]
    respond_by: Annotated[date, classified("internal")]
    days_left: Annotated[int, classified("internal")]


class NoticeFollowUpDue(DomainEvent):
    event_type: ClassVar[str] = "notice.follow_up_due"

    work_item_id: Annotated[UUID, classified("internal")]
    follow_up_on: Annotated[date, classified("internal")]


class NoticeResponseReadyToSend(DomainEvent):
    event_type: ClassVar[str] = "notice_response.ready_to_send"

    work_item_id: Annotated[UUID, classified("internal")]
    response_id: Annotated[UUID, classified("internal")]


class NoticeResponseSent(DomainEvent):
    event_type: ClassVar[str] = "notice.response_sent"

    work_item_id: Annotated[UUID, classified("internal")]
    sent_on: Annotated[date, classified("internal")]
    follow_up_on: Annotated[date, classified("internal")]
