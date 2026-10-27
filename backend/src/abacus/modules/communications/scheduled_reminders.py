"""The system's scheduled Reminder (R-01-T24; DEC-74; security review M2, H1; DEC-566, DEC-568).

The only place a `SystemSendContext` is built (banned-pattern COMM-002). The engagement agent's
P-4 tick only asks: "these overdue requests are due a reminder to this person". Communications
decides, on its own reads, whether anything goes:

1. the firm's policy says `send_on_schedule` and `follow_ups.scheduled_send` is on for the firm;
2. each named request is re-read here (`requests.api.overdue_for`) and kept only if it is still
   overdue for the same due date, a client may be written to about it (client-visible, not
   deleted, in a Published binder that is not closed), its binder is not marked done (when the
   policy stops there), the recipient is its client assignee, else one of the engagement's
   client admins, and its sequence is the next one the policy allows, recomputed from what was
   already sent (the cadence, the maximum; security review M-a);
3. the words are the firm's published Reminder, filled here from the kept requests' titles: the
   caller passes identifiers only, never text;
4. `send_templated` then applies its own checks (the version the firm published, attributed to
   its publisher; the lint on the version and on the values; the scope check; suppression).

Nothing kept, or a policy that doesn't send: None, and nothing is sent. Why this is a person's
decision and not the agent's: DEC-568.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel.clock import now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.modules.communications.follow_up_policy import (
    Sent,
    follow_up_policy,
    next_sequence_by_policy,
    reminder_history,
)
from abacus.modules.communications.notification_email import display_name
from abacus.modules.communications.template_registry import (
    RecipientRef,
    SendOutcome,
    SendScope,
    SystemSendContext,
    scheduled_send_enabled,
    send_templated,
)
from abacus.modules.identity.api import client_admins, firm_name, firm_time_zone, names_of
from abacus.modules.requests.api import OverdueItem, overdue_for

_MAX_ITEMS: Final = 10


@dataclass(frozen=True)
class ScheduledReminder:
    outcome: SendOutcome
    items: tuple[tuple[UUID, date, int], ...]  # what the reminder named: (request, due, sequence)


def _items_text(titles: Sequence[str]) -> str:
    lines = [" ".join(t.split()) for t in titles if t.strip()]
    shown = lines[:_MAX_ITEMS]
    if len(lines) > _MAX_ITEMS:
        shown.append(f"and {len(lines) - _MAX_ITEMS} more")
    return "\n".join(shown)


def _long_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


async def send_scheduled_reminder(
    tenant_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    items: Sequence[tuple[UUID, date, int]],
) -> ScheduledReminder | None:
    """Send the firm's Reminder for these overdue requests to this person, if the policy and
    every check allow it; None when nothing was sent (see the module docstring)."""
    system = TenantContext(tenant_id, "system", "follow_up:scheduled")
    policy = await follow_up_policy(system)
    if policy.mode != "send_on_schedule" or not await scheduled_send_enabled(system):
        return None
    zone = await firm_time_zone(system)
    today = (await now(system)).astimezone(ZoneInfo(zone)).date()
    overdue = {i.id: i for i in await overdue_for(system, engagement_id, today)}
    admins = set(await client_admins(system, engagement_id))
    history = await reminder_history(system, [i for i, _, _ in items])
    if history is None:
        return None  # nothing says what was already sent: fail closed
    kept: list[tuple[OverdueItem, int]] = []
    for item_id, due_on, sequence in items:
        found = overdue.get(item_id)
        if found is None or not found.sendable or found.due_on != due_on:
            continue
        if (
            found.binder_marked_done
            and policy.overridden(found.binder_override).stop_on_binder_done
        ):
            continue
        assignee = found.client_assignee_user_id
        if (assignee is not None and assignee != recipient_user_id) or (
            assignee is None and recipient_user_id not in admins
        ):
            continue
        # Security review M-a: the sequence is this request's next one under the policy (or the
        # binder's override), recomputed here from what was sent: never more than the maximum,
        # never sooner than the cadence, never a number the caller made up.
        rows = [at for i, d, _n, at in history if i == item_id and d == due_on]
        last = max(rows, default=None)
        sent = Sent(
            len(rows), last.astimezone(ZoneInfo(zone)).date() if last is not None else None
        )
        expected = next_sequence_by_policy(
            due_on, sent, today, policy.overridden(found.binder_override)
        )
        if expected is None or expected != sequence:
            continue
        kept.append((found, sequence))
    if not kept:
        return None
    name = (await names_of([recipient_user_id])).get(recipient_user_id, "")
    firm = await firm_name(tenant_id)
    values = {
        "client_first_name": " ".join(name.split()).partition(" ")[0],
        "firm_name": firm,
        "work_item": " ".join((await display_name(tenant_id, engagement_id)).split()),
        "open_items": _items_text([i.description for i, _ in kept]),
        "due_date": _long_date(min(i.due_on for i, _ in kept)),
        # The portal's sign-in, with no token (DEC-566).
        "portal_link": f"{settings().app_base_url.rstrip('/')}/portal",
        "staff_name": firm,
    }
    named = tuple((i.id, i.due_on, n) for i, n in kept)
    key = f"p4:{engagement_id}:{recipient_user_id}:" + ",".join(
        f"{i}:{d.isoformat()}:{n}" for i, d, n in named
    )
    outcome = await send_templated(
        SystemSendContext(
            tenant=system, reason="scheduled_follow_up", policy_version=policy.version
        ),
        "reminder",
        RecipientRef("user", recipient_user_id),
        values,
        scope=SendScope(engagement_id),
        idempotency_key=hashlib.sha256(key.encode()).hexdigest(),
    )
    return ScheduledReminder(outcome, named)
