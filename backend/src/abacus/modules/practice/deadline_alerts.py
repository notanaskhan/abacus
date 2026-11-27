"""The filing-deadline T-7 and T-1 notices (T-08-T21; TASK-9016; SPEC-710; DEC-6022).

After each firm's nightly recompute, every open deadline due within seven days of the firm's
today (in the firm's zone) reaches a threshold: `t_minus_7` while more than one day is left,
`t_minus_1` once one day or less is. Each (deadline, threshold, due date) is written once to the
insert-only `filing_deadline_alerts` (0962), so a re-run, a retry or a second worker never sends a
second notice; a deadline whose date moves (an extension, a relief notice) is a new due date and
may be told again. A deadline first seen inside one day (a late recompute) is told once, at
`t_minus_1`: its `t_minus_7` row is written as passed, with no notice.

The notice is `filing_deadline.approaching` to the deadline's owners and signer, less anyone
walled from its client (metadata only: the payload names the deadline and the threshold, never a
TIN or an amount). Overdue and done deadlines are never told.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.clock import FIRM_ZONE
from abacus.kernel.clock import now as clock_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import walled_from
from abacus.modules.practice.compute import deadlines as calc

Threshold = Literal["t_minus_7", "t_minus_1"]
WINDOW: Final = 7
ACTION: Final = "filing_deadline.approaching"
ACTOR: Final = "practice:filing_deadline_alerts"


class FilingDeadlineApproaching(DomainEvent):
    """T-08-T21: an open filing deadline reached T-7 or T-1 in the firm's zone."""

    event_type: ClassVar[str] = ACTION

    filing_deadline_id: Annotated[UUID, classified("internal")]
    threshold: Annotated[str, classified("internal")]
    due_on: Annotated[date, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


@dataclass(frozen=True)
class Due:
    deadline_id: UUID
    client_id: UUID | None
    due_on: date
    people: tuple[UUID, ...]


def threshold_for(days_left: int) -> Threshold | None:
    """The tightest threshold a deadline `days_left` away has reached (None: not yet, or past)."""
    if days_left < 0 or days_left > WINDOW:
        return None
    return "t_minus_1" if days_left <= 1 else "t_minus_7"


_OPEN = text(
    "SELECT id, client_id, due_on, owner_user_ids, signer_user_id FROM filing_deadlines "
    "WHERE done_at IS NULL AND due_on BETWEEN :f AND :t ORDER BY due_on, id"
)
_ALERT = text(
    "INSERT INTO filing_deadline_alerts (tenant_id, filing_deadline_id, threshold, due_on) "
    "VALUES (:tn, :d, :th, :due) ON CONFLICT (filing_deadline_id, threshold, due_on) DO NOTHING "
    "RETURNING id"
)


async def _open(tenant: TenantContext, today: date) -> list[Due]:
    async with tenant_session(tenant) as session:
        found = await session.execute(_OPEN, {"f": today, "t": today + timedelta(days=WINDOW)})
        return [
            Due(
                cast(UUID, r[0]), cast(UUID | None, r[1]), cast(date, r[2]),
                tuple(dict.fromkeys([*cast(list[UUID], r[3]), *([r[4]] if r[4] else [])])),
            )
            for r in found
        ]  # fmt: skip


async def _recipients(tenant: TenantContext, due: Due) -> list[UUID]:
    if due.client_id is None:
        return sorted(due.people)
    return sorted(
        [p for p in due.people if due.client_id not in await walled_from(tenant, p)]
    )  # fmt: skip


async def sweep(tenant_id: UUID, *, today: date | None = None) -> int:
    """One firm's T-7 and T-1 notices; answers how many were sent."""
    tenant = TenantContext(tenant_id, "system", ACTOR)
    if today is None:
        today = calc.firm_today(await clock_now(tenant), str(FIRM_ZONE))
    sent = 0
    for due in await _open(tenant, today):
        reached = threshold_for((due.due_on - today).days)
        if reached is None:
            continue
        people = await _recipients(tenant, due)
        try:
            await _tell(tenant, due, reached, people)
        except _AlreadyTold:
            continue
        sent += 1
    return sent


class _AlreadyTold(Exception):
    """This threshold was told for this due date already: the unit of work rolls back."""


async def _tell(tenant: TenantContext, due: Due, reached: Threshold, people: list[UUID]) -> None:
    tenant_id = tenant.tenant_id
    async with uow(tenant) as tx:
        if reached == "t_minus_1":  # a T-7 not yet told is passed, never sent late
            await tx.session.execute(
                _ALERT,
                {"tn": tenant_id, "d": due.deadline_id, "th": "t_minus_7", "due": due.due_on},
            )
        written = await tx.session.execute(
            _ALERT, {"tn": tenant_id, "d": due.deadline_id, "th": reached, "due": due.due_on}
        )
        if written.first() is None:
            raise _AlreadyTold
        tx.record(
            ACTION,
            target=Target("filing_deadline", due.deadline_id),
            after=Ref(days=WINDOW if reached == "t_minus_7" else 1),
        )
        tx.emit(
            FilingDeadlineApproaching(
                filing_deadline_id=due.deadline_id,
                threshold=reached,
                due_on=due.due_on,
                recipient_user_ids=people,
            )
        )


__all__ = ["FilingDeadlineApproaching", "sweep", "threshold_for"]
