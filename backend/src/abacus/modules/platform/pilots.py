"""Pilot enrolments (Q-04-T007; Q-04 §4; DEC-716): a work item enters a pilot window in shadow
mode, goes live, and becomes the system of record only with a named person's confirmation (the
table's CHECK agrees). Operators enrol through `make pilot-enrol` (`abacus_tools.pilots`); each
change is one unit of work with its audit event.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Target, uow

Mode = Literal["shadow", "live", "system_of_record", "exited"]
_NEXT: Final[dict[str, frozenset[str]]] = {
    "shadow": frozenset({"live", "exited"}),
    "live": frozenset({"system_of_record", "exited"}),
    "system_of_record": frozenset({"exited"}),
    "exited": frozenset(),
}


# The audit trail's references hold UUIDs and integers only, so a mode is recorded by its number.
MODE_NUMBER: Final[dict[str, int]] = {"shadow": 1, "live": 2, "system_of_record": 3, "exited": 4}


class PilotModeRefused(DomainConflict):
    """The enrolment cannot move to that mode from where it is (or without a confirming person)."""

    code = "pilot_mode_refused"


async def enrol(
    tenant: TenantContext,
    work_item_id: UUID,
    window_start: date,
    window_end: date,
    baseline_days: int | None,
    created_by: UUID,
) -> UUID:
    async with uow(tenant) as tx:
        found = await tx.session.scalar(
            text(
                "INSERT INTO pilot_enrolments (tenant_id, work_item_id, window_start, window_end, "
                "baseline_days, created_by) VALUES (:t, :w, :s, :e, :b, :c) RETURNING id"
            ),
            {
                "t": tenant.tenant_id,
                "w": work_item_id,
                "s": window_start,
                "e": window_end,
                "b": baseline_days,
                "c": created_by,
            },
        )
        enrolment = UUID(str(found))
        tx.record(
            "pilot.enrolled",
            target=Target("pilot_enrolment", enrolment),
            after=Ref(work_item=work_item_id, mode=MODE_NUMBER["shadow"]),
        )
    return enrolment


async def set_mode(
    tenant: TenantContext, enrolment_id: UUID, mode: Mode, confirmed_by: UUID | None = None
) -> None:
    async with uow(tenant) as tx:
        current = await tx.session.scalar(
            text("SELECT mode FROM pilot_enrolments WHERE id = :id FOR UPDATE"),
            {"id": enrolment_id},
        )
        if current is None or mode not in _NEXT[str(current)]:
            raise PilotModeRefused(facts={"mode": mode})
        if mode == "system_of_record" and confirmed_by is None:
            raise PilotModeRefused(facts={"mode": mode, "reason": "confirming_person"})
        await tx.session.execute(
            text(
                "UPDATE pilot_enrolments SET mode = :m, updated_at = clock_timestamp(), "
                "confirmed_by = coalesce(CAST(:c AS uuid), confirmed_by), "
                "confirmed_at = CASE WHEN :m = 'system_of_record' THEN clock_timestamp() "
                "ELSE confirmed_at END WHERE id = :id"
            ),
            {"m": mode, "c": confirmed_by, "id": enrolment_id},
        )
        tx.record(
            "pilot.mode_changed",
            target=Target("pilot_enrolment", enrolment_id),
            before=Ref(mode=MODE_NUMBER[str(current)]),
            after=Ref(mode=MODE_NUMBER[mode], confirmed_by=confirmed_by)
            if confirmed_by is not None
            else Ref(mode=MODE_NUMBER[mode]),
        )
