"""`NoticeResponseWorkflow`'s input and signals (N-04-T16): identifiers and dates only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NoticeResponseInput:
    tenant_id: str
    work_item_id: str
    respond_by: str | None  # ISO date
    notice_type_key: str
    follow_up_on: str | None = None
    fired: tuple[int, ...] = ()


@dataclass(frozen=True)
class AlertInput:
    tenant_id: str
    work_item_id: str
    respond_by: str
    days_left: int


@dataclass(frozen=True)
class FollowUpInput:
    tenant_id: str
    work_item_id: str
    follow_up_on: str
