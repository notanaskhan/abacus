"""The work-item facts another module's list filters, groups and shows (P-06-T11; BND-01).

A binder hangs on a work item (DEC-31), so the binders index reads its service (the work item's
kind), season, office, preparer, client and name from here rather than from engagements' tables.
It is a subquery the list joins on `id`: it reads under the caller's session (RLS), and the
joining list applies `visible()` to its own rows (LIST-001), so it can show nothing that list
would hide.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement, Integer, Subquery, case, cast, column, func, select, table

from abacus.modules.engagements.models import WorkItem
from abacus.modules.organisations.api import client_name_column, office_name_column

_assignments = table(
    "work_item_assignments",
    column("tenant_id"),
    column("work_item_id"),
    column("user_id"),
    column("function"),
    column("assigned_at"),
    column("removed_at"),
)
PREPARER_FUNCTIONS: Final = ("preparer", "close_preparer")
_TAX_RETURN: Final = "tax_return"


def _preparer(work_item_id: ColumnElement[UUID]) -> ColumnElement[UUID]:
    """The person holding a preparer function now: the newest assignment that no later removal
    row undoes (assignments are insert-only; a removal is a new row with `removed_at`)."""
    added, removed = _assignments.alias("added"), _assignments.alias("removed")
    undone = (
        select(removed.c.user_id)
        .where(
            removed.c.work_item_id == added.c.work_item_id,
            removed.c.user_id == added.c.user_id,
            removed.c.function == added.c.function,
            removed.c.removed_at.is_not(None),
            removed.c.assigned_at >= added.c.assigned_at,
        )
        .exists()
    )
    return (
        select(added.c.user_id)
        .where(
            added.c.work_item_id == work_item_id,
            added.c.function.in_(PREPARER_FUNCTIONS),
            added.c.removed_at.is_(None),
            ~undone,
        )
        .order_by(added.c.assigned_at.desc())
        .limit(1)
        .correlate_except(added, removed)
        .scalar_subquery()
    )


def _season() -> ColumnElement[str | None]:
    """The season a list groups work by. A return's tax year is the year its period begins (a
    fiscal-year 990 for Jul 2025 to Jun 2026 is TY2025); other work reads its fiscal year end
    (FY2026). No period, no season."""
    start = cast(func.extract("year", WorkItem.period_start), Integer)
    end = cast(func.extract("year", WorkItem.period_end), Integer)
    return case(
        (
            (WorkItem.kind == _TAX_RETURN) & WorkItem.period_start.is_not(None),
            func.concat("TY", start),
        ),
        (
            (WorkItem.kind != _TAX_RETURN) & WorkItem.period_end.is_not(None),
            func.concat("FY", end),
        ),
        else_=None,
    )


def work_item_index() -> Subquery:
    """Per work item: `id`, `engagement_id`, `kind`, `name`, `client_id`, `client_name`,
    `office_id`, `office_name`, `season` and `preparer_user_id`."""
    return select(
        WorkItem.id.label("id"),
        WorkItem.engagement_id.label("engagement_id"),
        WorkItem.kind.label("kind"),
        WorkItem.name.label("name"),
        WorkItem.client_id.label("client_id"),
        client_name_column(WorkItem.client_id).label("client_name"),
        WorkItem.office_id.label("office_id"),
        office_name_column(WorkItem.office_id).label("office_name"),
        _season().label("season"),
        _preparer(WorkItem.id.expression).label("preparer_user_id"),
    ).subquery("work_item_index")
