"""The returns' filing deadlines as facts (T-08-T10; S51 partials, TASK-8741; DEC-5732), for
practice's recompute (practice reads tax; tax never imports practice). Metadata only: the work
item, engagement, form and tax year, the dates T-02's due-date rules stored on the return
(original and extended due dates, their reference-set versions), the stage and whether filed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

DONE: Final = frozenset({"filed", "accepted"})
_RETURNS = text(
    "SELECT work_item_id, engagement_id, form, tax_year, status, extended, original_due_on, "
    "extended_due_on, due_rule_version_ids FROM tax_returns WHERE original_due_on IS NOT NULL "
    "AND coalesce(on_hold, false) = false ORDER BY work_item_id"
)


@dataclass(frozen=True)
class ReturnDeadline:
    work_item_id: UUID
    engagement_id: UUID | None
    form: str
    tax_year: int
    stage_code: str
    extended: bool
    original_due_on: date
    extended_due_on: date | None
    reference_set_version_ids: tuple[UUID, ...]

    @property
    def done(self) -> bool:
        return self.stage_code in DONE

    @property
    def label(self) -> str:
        return f"Form {self.form} · {self.tax_year}"


async def return_deadlines(tenant: TenantContext) -> list[ReturnDeadline]:
    async with tenant_session(tenant) as session:
        rows = [tuple(r) for r in await session.execute(_RETURNS)]
    out: list[ReturnDeadline] = []
    for r in rows:
        ids: list[UUID] = []
        for raw in cast(list[object], r[8] or []):
            try:
                ids.append(UUID(str(raw)))
            except ValueError:
                continue
        out.append(
            ReturnDeadline(
                cast(UUID, r[0]), cast(UUID | None, r[1]), str(r[2]), int(cast(int, r[3])),
                str(r[4]), bool(r[5]), cast(date, r[6]), cast(date | None, r[7]), tuple(ids),
            )
        )  # fmt: skip
    return out


__all__ = ["ReturnDeadline", "return_deadlines"]
