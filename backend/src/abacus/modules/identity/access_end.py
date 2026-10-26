"""Seasonal access end as a platform job (G-01-T13; G-01 AC4.5, R-7; DEC-381).

`AccessEndSweepWorkflow` runs `sweep_access_ends()` every hour on the Schedule
`access_end:platform` (`kernel.dispatch`; overlap SKIP, one hour catch-up), so a member whose
`access_ends_on` has passed in their firm's time zone (`kernel.clock`, the firm's demo clock
included) is deactivated within the hour after that firm's midnight, with no manual step.
For each firm:

- **Ends access** for every active staff member whose end date is before the firm's business
  date: the membership is revoked with reason `access_ended` (ADM-02e dates it by the end date),
  the seat frees, their sessions end when no other firm holds them, their pending invitations
  end, and `membership.deactivated` and `access.changed` are published. The audit row is the
  system's, on behalf of the person who last set the date (read from the audit trail; "Access
  ended · set by …"). The date is read again under a row lock, so a date moved since the list
  was read is respected, and a run finds nothing left to do the second time (idempotent). The
  firm's last firm or security admin is never ended (logged and skipped, as the definer
  refuses).
- **Tells firm admins once**, seven days or fewer before an end date (`seasonal_access_ending`),
  one notice per firm and date (`access_end_notices`).

Firms are listed through the identity role, which already reads `firms.tenant_id`; everything
else runs inside each firm's own session (row-level security). A failing firm is logged at error
(`access_end.firm_failed`) and counted (`abacus.access_end.firm_failed`), and the others still run.

The job is the state change, the notices and the audit; it is not what keeps a member out. Access
ends at request time too (`access_window.access_has_ended`, read by `routing.current_context`,
by `authorise` for an agent's initiator and by `/v1/me`; DEC-383): a
staff member whose end date is before the firm's business date is refused whether or not a sweep
ran, so a stopped Schedule can't extend access. Each pass is counted (`abacus.access_end.sweep`,
by outcome) and, when neither of the two runs before it succeeded (no successful sweep in two
hours), logged at error as `access_end.stale` and counted (`abacus.access_end.stale`).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import schedule_results
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, audit_of_targets, uow
from abacus.modules.identity import people_repository as repo
from abacus.modules.identity.access_window import firm_zone
from abacus.modules.identity.events import (
    AccessChanged,
    MembershipDeactivated,
    SeasonalAccessEnding,
)
from abacus.modules.identity.invitations import revoke_invitations_by
from abacus.modules.identity.people import revoke_invitations_of
from abacus.modules.identity.repository import (
    firm_tenant_ids,
    memberships_elsewhere,
)
from abacus.modules.identity.workflows import ACCESS_END_ID

NOTICE_DAYS: Final = 7
_ACTOR: Final = "identity:access_end"
_ACCESS_ENDED: Final = 2  # `people._REASON_INDEX["access_ended"]`
_log = get_logger(__name__)
_sweeps = meter(__name__).create_counter(
    "abacus.access_end.sweep", description="Access-end passes, by outcome (ok, partial, failed)"
)
_firm_failures = meter(__name__).create_counter(
    "abacus.access_end.firm_failed", description="Firms an access-end pass could not sweep"
)
_stale = meter(__name__).create_counter(
    "abacus.access_end.stale", description="Passes after two runs with no successful sweep"
)


@dataclass(frozen=True)
class Sweep:
    firms: int
    ended: int
    notices: int
    failed_firms: int = 0


class _Skip(Exception):
    """Nothing to write for this member after all: the unit of work rolls back."""


_ENDING = text(
    "SELECT user_id, access_ends_on FROM memberships WHERE kind = 'staff' AND status = 'active' "
    "AND access_ends_on IS NOT NULL ORDER BY access_ends_on, user_id"
)


async def _set_by(tenant: TenantContext, user_id: UUID) -> UUID | None:
    """Who last set the person's access end date: the newest person-made attribute change that
    named it (the bulk Seasonal date and the drawer both record one)."""
    async with tenant_session(tenant) as session:
        events = await audit_of_targets(
            session, [("user", user_id)], None, 50, action="membership.attributes_changed"
        )
    for event in events:
        if (
            event.actor_kind == "human"
            and event.after_ref is not None
            and "access_ends_on" in event.after_ref
        ):
            try:
                return UUID(event.actor_id)
            except ValueError:
                break
    # The date came with the invitation or the seed: the system ends access on its own behalf.
    _log.info("access_end.setter_unknown", tenant_id=tenant.tenant_id, user_id=user_id)
    return None


async def _end(tenant_id: UUID, user_id: UUID, today: date) -> bool:
    setter = await _set_by(TenantContext(tenant_id, "system", _ACTOR), user_id)
    elsewhere = await memberships_elsewhere(tenant_id, [user_id])
    system = TenantContext(tenant_id, "system", _ACTOR, setter)
    try:
        async with uow(system) as tx:
            ends = await tx.session.scalar(
                text(
                    "SELECT access_ends_on FROM memberships WHERE user_id = :u AND kind = 'staff' "
                    "AND status = 'active' FOR UPDATE"
                ),
                {"u": user_id},
            )
            if ends is None or cast(date, ends) >= today:
                raise _Skip  # ended already, or the date moved since the list was read
            outcome = await repo.deactivate(
                tx.session,
                user_id,
                "access_ended",
                setter,
                end_sessions=not elsewhere.get(user_id, False),
            )
            if outcome != "ok":
                _log.warning("access_end.kept", tenant_id=tenant_id, outcome=outcome)
                raise _Skip
            tx.record(
                "membership.deactivated",
                target=Target("user", user_id),
                after=Ref(reason=_ACCESS_ENDED),
            )
            await revoke_invitations_of(tx, user_id, include_to=True)
            await revoke_invitations_by(tx, user_id)
            tx.emit(MembershipDeactivated(user_id=user_id))
            tx.emit(AccessChanged(user_id=user_id))
    except _Skip:
        return False
    return True


async def _notice(tenant_id: UUID, ends: date, members: int) -> bool:
    try:
        async with uow(TenantContext(tenant_id, "system", _ACTOR)) as tx:
            inserted = await tx.session.scalar(
                text(
                    "INSERT INTO access_end_notices (tenant_id, access_ends_on, members) "
                    "VALUES (:tenant, :ends, :members) "
                    "ON CONFLICT (tenant_id, access_ends_on) DO NOTHING RETURNING members"
                ),
                {"tenant": tenant_id, "ends": ends, "members": members},
            )
            if inserted is None:
                raise _Skip  # told already
            tx.record(
                "membership.access_ending_notified",
                target=Target("firm", tenant_id),
                after=Ref(members=members),
            )
            tx.emit(SeasonalAccessEnding(access_ends_on=ends, members=members))
    except _Skip:
        return False
    return True


async def sweep_firm(tenant_id: UUID) -> tuple[int, int]:
    """One firm's pass: (members ended, notices sent)."""
    system = TenantContext(tenant_id, "system", _ACTOR)
    async with tenant_session(system) as session:
        rows = [
            (cast(UUID, r[0]), cast(date, r[1])) for r in (await session.execute(_ENDING)).all()
        ]
    if not rows:
        return 0, 0
    today = await clock.today(system, await firm_zone(system))
    ended = 0
    for user_id, ends in rows:
        if ends < today and await _end(tenant_id, user_id, today):
            ended += 1
    horizon = today + timedelta(days=NOTICE_DAYS)
    upcoming = Counter(ends for _, ends in rows if today <= ends <= horizon)
    notices = 0
    for ends, members in sorted(upcoming.items()):
        if await _notice(tenant_id, ends, members):
            notices += 1
    return ended, notices


async def sweep_access_ends() -> Sweep:
    """One pass over every firm (AC4.5); idempotent."""
    firms = await firm_tenant_ids()
    ended = notices = failed = 0
    for tenant_id in firms:
        try:
            firm_ended, firm_notices = await sweep_firm(tenant_id)
        except Exception as exc:  # one firm's failure never stops the others
            failed += 1
            _firm_failures.add(1)
            _log.error("access_end.firm_failed", tenant_id=tenant_id, error=type(exc).__name__)
            continue
        ended += firm_ended
        notices += firm_notices
    _log.info(
        "access_end.swept", firms=len(firms), ended=ended, notices=notices, failed_firms=failed
    )
    return Sweep(len(firms), ended, notices, failed)


def stale(previous_succeeded: list[bool]) -> bool:
    """No successful sweep in two hours: the two runs before this one both failed."""
    return len(previous_succeeded) >= 2 and not any(previous_succeeded[:2])


@activity.defn(name="identity.sweep_access_ends")
async def sweep_access_ends_activity() -> int:
    try:
        previous = await schedule_results(
            ACCESS_END_ID, exclude_run_id=activity.info().workflow_run_id, limit=2
        )
        if stale([run.completed for run in previous]):
            _stale.add(1)
            _log.error("access_end.stale", schedule=ACCESS_END_ID)
    except Exception as exc:  # the staleness read never stops the sweep
        _log.warning("access_end.stale_unknown", error=type(exc).__name__)
    try:
        swept = await sweep_access_ends()
    except Exception:
        _sweeps.add(1, {"outcome": "failed"})
        raise
    _sweeps.add(1, {"outcome": "partial" if swept.failed_firms else "ok"})
    return swept.ended
