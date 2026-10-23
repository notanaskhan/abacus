"""What engagements tells evidence about legal-hold scopes (Q-02-T29; DEC-228). Registered in
`api.py`; evidence never reads these tables itself.

A hold names a client, a client and tax year, an engagement or a work item. Evidence versions
belong to engagements, so a scope comes down to engagement ids. A tax year covers every engagement
of the client whose fiscal period, or any of whose work items' periods, overlaps that calendar
year: a fiscal year starting in the tax year overlaps it, and so does the one ending in it.
Holding more than asked is the safe error for a preservation duty; holding less is not.
Archived and declined engagements are included: a hold is about the records, not the work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import and_, exists, or_, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.models import Engagement, WorkItem


@dataclass(frozen=True)
class EngagementHoldFacts:
    """An engagement's place in hold scopes: its client and the calendar years it touches."""

    engagement_id: UUID
    client_id: UUID
    years: frozenset[int]
    work_item_ids: frozenset[UUID]


def _years(start: date | None, end: date | None) -> set[int]:
    lo, hi = start or end, end or start
    if lo is None or hi is None:
        return set()
    return set(range(lo.year, hi.year + 1))


async def engagement_hold_facts(
    tenant: TenantContext, engagement_id: UUID
) -> EngagementHoldFacts | None:
    """The engagement's client, the calendar years its period and its work items' periods
    overlap, and its work items; None when it isn't in the tenant."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                select(
                    Engagement.client_id,
                    Engagement.fiscal_period_start,
                    Engagement.fiscal_period_end,
                ).where(Engagement.id == engagement_id)
            )
        ).one_or_none()
        if row is None:
            return None
        items = (
            await session.execute(
                select(WorkItem.id, WorkItem.period_start, WorkItem.period_end).where(
                    WorkItem.engagement_id == engagement_id
                )
            )
        ).all()
    years = _years(row.fiscal_period_start, row.fiscal_period_end)
    for _id, start, end in items:
        years |= _years(start, end)
    return EngagementHoldFacts(
        engagement_id, row.client_id, frozenset(years), frozenset(i for i, _s, _e in items)
    )


async def engagements_in_hold_scope(
    tenant: TenantContext, client_id: UUID, tax_year: int | None = None
) -> list[UUID]:
    """Every engagement of the client (any status), or only those touching `tax_year`."""
    first = date(tax_year, 1, 1) if tax_year is not None else None
    last = date(tax_year, 12, 31) if tax_year is not None else None
    query = select(Engagement.id).where(Engagement.client_id == client_id)
    if first is not None and last is not None:
        item_touches = exists().where(
            WorkItem.engagement_id == Engagement.id,
            or_(WorkItem.period_start.is_not(None), WorkItem.period_end.is_not(None)),
            or_(WorkItem.period_start.is_(None), WorkItem.period_start <= last),
            or_(WorkItem.period_end.is_(None), WorkItem.period_end >= first),
        )
        query = query.where(
            or_(
                and_(
                    Engagement.fiscal_period_start <= last,
                    Engagement.fiscal_period_end >= first,
                ),
                item_touches,
            )
        )
    async with tenant_session(tenant) as session:
        return list((await session.scalars(query.order_by(Engagement.id))).all())


async def work_item_engagement(tenant: TenantContext, work_item_id: UUID) -> UUID | None:
    """The work item's engagement, or None outside the tenant."""
    async with tenant_session(tenant) as session:
        return await session.scalar(
            select(WorkItem.engagement_id).where(WorkItem.id == work_item_id)
        )


__all__ = [
    "EngagementHoldFacts",
    "engagement_hold_facts",
    "engagements_in_hold_scope",
    "work_item_engagement",
]
