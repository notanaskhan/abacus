"""Envelope reminders (N-02-T14; N-02 §3.7; DEC-74).

A person picks the cadence at Send; the system then runs it: weekdays at 9:00 in the recipient's
zone, never after expiry, never beyond the policy's cap. A reminder goes out only from the
firm's human-approved `signature_reminder` template, sent by communications through the sender it
registers here. Until one is registered, a due reminder is recorded as skipped and nothing is
sent (fail closed). The agent never schedules or sends one (INV-1).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel.db import TenantContext

SEND_AT: Final = time(9, 0)
# Business days between reminders, per cadence a person may choose (`envelope_policies`).
CADENCE_DAYS: Final[dict[str, int]] = {
    "daily": 1,
    "every_2_days": 2,
    "every_3_days": 3,
    "weekly": 5,
}

# communications: send the `signature_reminder` template's published version to one signer;
# True when it was queued, False when a check refused it.
ReminderSender = Callable[[TenantContext, UUID, UUID, int], Awaitable[bool]]
_sender: ReminderSender | None = None


def register_reminder_sender(sender: ReminderSender | None) -> None:
    global _sender
    _sender = sender


def reminder_sender() -> ReminderSender | None:
    return _sender


def _add_weekdays(day: date, n: int) -> date:
    while n > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def reminder_instants(
    *,
    cadence: str | None,
    sent_at: datetime,
    expires_at: datetime,
    cap: int,
    zone: str,
) -> list[datetime]:
    """When each reminder is due, in UTC: every `cadence` business days after the send, at 9:00
    in `zone`, strictly between the send and the expiry, at most `cap`. An unknown or empty
    cadence schedules nothing."""
    step = CADENCE_DAYS.get(cadence or "")
    if step is None or cap <= 0:
        return []
    tz = ZoneInfo(zone)
    day = sent_at.astimezone(tz).date()
    out: list[datetime] = []
    while len(out) < cap:
        day = _add_weekdays(day, step)
        at = datetime.combine(day, SEND_AT, tzinfo=tz).astimezone(ZoneInfo("UTC"))
        if at >= expires_at:
            break
        if at > sent_at:
            out.append(at)
    return out
