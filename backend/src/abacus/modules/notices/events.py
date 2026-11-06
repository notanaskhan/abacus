"""Notice events (N-04-T16; N-04 §4.7): identifiers, counts and dates only, no amounts (DEC-61)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class NoticeIntakeStarted(DomainEvent):
    """An intake waits for code to read its file: starts `NoticeIntakeWorkflow` (N-04-T07)."""

    event_type: ClassVar[str] = "notice_intake.started"

    intake_id: Annotated[UUID, classified("internal")]


class NoticeAnalysisRequested(DomainEvent):
    """A person ran the analysis: starts `NoticeAnalysisWorkflow` for this running version."""

    event_type: ClassVar[str] = "notice_analysis.requested"

    notice_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]


class NoticeIntakeReady(DomainEvent):
    """Read, or opened for manual entry: the intake's owner may act (N-04 §4.6)."""

    event_type: ClassVar[str] = "notice_intake.ready"

    intake_id: Annotated[UUID, classified("internal")]
    owner_id: Annotated[UUID, classified("internal")]


class NoticeCreated(DomainEvent):
    event_type: ClassVar[str] = "notice.created"

    work_item_id: Annotated[UUID, classified("internal")]
    # N-04-T07 (additive): who hears of it (the assignee; the signing partner when toggled).
    assignee_id: Annotated[UUID | None, classified("internal")] = None
    notify_user_ids: Annotated[tuple[UUID, ...], classified("internal")] = ()


class NoticeRespondBySoon(DomainEvent):
    event_type: ClassVar[str] = "notice.respond_by_soon"

    work_item_id: Annotated[UUID, classified("internal")]
    respond_by: Annotated[date, classified("internal")]
    days_left: Annotated[int, classified("internal")]
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None  # C16's recipient


class NoticeFollowUpDue(DomainEvent):
    event_type: ClassVar[str] = "notice.follow_up_due"

    work_item_id: Annotated[UUID, classified("internal")]
    follow_up_on: Annotated[date, classified("internal")]
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None  # C16's recipient


class NoticeResponseReadyToSend(DomainEvent):
    event_type: ClassVar[str] = "notice_response.ready_to_send"

    work_item_id: Annotated[UUID, classified("internal")]
    response_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None  # I-01-T23: C13's key
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None  # C16's recipient


class NoticeResponseSent(DomainEvent):
    event_type: ClassVar[str] = "notice.response_sent"

    work_item_id: Annotated[UUID, classified("internal")]
    sent_on: Annotated[date, classified("internal")]
    follow_up_on: Annotated[date, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None  # I-01-T23: C13's key
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None  # C16's recipient
