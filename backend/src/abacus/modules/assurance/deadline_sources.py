"""Plan-audit dates as filing-deadline facts (T-08-T20; TASK-8915; FD-1; HOME-03; DEC-5917).
Registered to platform's slot as kinds `form_5500` and `assurance_report`; practice never imports
assurance. Metadata only.

- **Form 5500** (one per EBP plan audit): the last day of the seventh month after the plan year
  ends (29 CFR 2520.104a-5; Form 5500 instructions), rolled past a weekend; Form 5558 extends it
  two and a half months (the 15th day of the tenth month), shown whenever known and used once the
  5558 is filed. The plan sponsor files it; done once the audit report is released (the report
  the filing attaches).
- **Report target** (one per plan audit with a target date): the firm's report target; done once
  the report is released.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import FilingDeadlineFact, FilingDeadlineWindow

OWNER_ROLES: Final = frozenset({"senior", "staff", "reviewer", "manager"})
_PLANS: Final = text(
    "SELECT p.work_item_id, p.engagement_id, p.plan_year_end, p.form_5558_filed_on, "
    "p.report_target_on, EXISTS (SELECT 1 FROM report_releases x WHERE x.work_item_id = "
    "p.work_item_id) AS released FROM ebp_plans p ORDER BY p.work_item_id"
)


def _end_of_month(year: int, month: int) -> date:
    year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    following = date(year + (month == 12), month % 12 + 1, 1)
    return following - timedelta(days=1)


def _roll(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def form_5500_due(plan_year_end: date) -> tuple[date, date]:
    """(due, extended due): the seventh month's last day after the plan year end, and the 15th
    day of the tenth month with Form 5558; both rolled past a weekend."""
    due = _end_of_month(plan_year_end.year, plan_year_end.month + 7)
    month = plan_year_end.month + 10
    extended = date(plan_year_end.year + (month - 1) // 12, (month - 1) % 12 + 1, 15)
    return _roll(due), _roll(extended)


async def _teams(
    tenant: TenantContext, engagements: Sequence[UUID]
) -> dict[UUID, tuple[UUID | None, UUID | None, tuple[UUID, ...], UUID | None]]:
    from abacus.modules.engagements.api import engagement_retention_facts
    from abacus.modules.identity.api import team_of

    facts = await engagement_retention_facts(tenant, sorted(set(engagements), key=str))
    out: dict[UUID, tuple[UUID | None, UUID | None, tuple[UUID, ...], UUID | None]] = {}
    for engagement in sorted(set(engagements), key=str):
        team = await team_of(tenant.tenant_id, engagement)
        f = facts.get(engagement)
        out[engagement] = (
            None if f is None else f.client_id,
            None if f is None else f.office_id,
            tuple(sorted({u for u, r in team if str(r) in OWNER_ROLES}, key=str)),
            next((u for u, r in team if str(r) == "engagement_partner"), None),
        )
    return out


@dataclass(frozen=True)
class _Plan:
    work_item_id: UUID
    engagement_id: UUID
    plan_year_end: date
    form_5558_filed_on: date | None
    report_target_on: date | None
    released: bool


async def _plans(tenant: TenantContext) -> list[_Plan]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PLANS)).all()
    return [
        _Plan(r.work_item_id, r.engagement_id, r.plan_year_end, r.form_5558_filed_on,
              r.report_target_on, bool(r.released))
        for r in rows
    ]  # fmt: skip


async def form_5500_deadlines(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    t = cast(TenantContext, tenant)
    rows: list[tuple[_Plan, date, date, date, date | None]] = []
    for r in await _plans(t):
        due, extended = form_5500_due(r.plan_year_end)
        filed_5558 = r.form_5558_filed_on
        current = extended if filed_5558 is not None else due
        if window.start <= current <= window.end:
            rows.append((r, due, extended, current, filed_5558))
    teams = await _teams(t, [r.engagement_id for r, *_ in rows])
    out: list[FilingDeadlineFact] = []
    for r, due, extended, current, filed_5558 in rows:
        client, office, owners, signer = teams[r.engagement_id]
        year_end = r.plan_year_end
        out.append(
            FilingDeadlineFact(
                source_kind="form_5500",
                source_ref=f"form_5500:{r.work_item_id}",
                filing_label=f"Form 5500 · plan year {year_end.year}",
                client_id=client,
                office_id=office,
                service_line="audit",
                original_due_on=due,
                due_on=current,
                stage_code="released" if r.released else "fieldwork",
                owner_user_ids=owners,
                signer_user_id=signer,
                extension_form="5558",
                extension_filed_on=filed_5558,
                extended_due_on=extended,
                done=bool(r.released),
                work_item_id=r.work_item_id,
            )
        )
    return out


async def report_target_deadlines(
    tenant: object, window: FilingDeadlineWindow
) -> Sequence[FilingDeadlineFact]:
    t = cast(TenantContext, tenant)
    rows = [
        r
        for r in await _plans(t)
        if r.report_target_on is not None and window.start <= r.report_target_on <= window.end
    ]
    teams = await _teams(t, [r.engagement_id for r in rows])
    out: list[FilingDeadlineFact] = []
    for r in rows:
        client, office, owners, signer = teams[r.engagement_id]
        target = cast(date, r.report_target_on)
        out.append(
            FilingDeadlineFact(
                source_kind="assurance_report",
                source_ref=f"report_target:{r.work_item_id}",
                filing_label="Audit report target",
                client_id=client,
                office_id=office,
                service_line="audit",
                original_due_on=target,
                due_on=target,
                stage_code="released" if r.released else "fieldwork",
                owner_user_ids=owners,
                signer_user_id=signer,
                done=bool(r.released),
                work_item_id=r.work_item_id,
            )
        )
    return out


def register() -> None:
    from abacus.modules.platform.api import register_filing_deadline_source

    register_filing_deadline_source("form_5500", form_5500_deadlines)
    register_filing_deadline_source("assurance_report", report_target_deadlines)


__all__ = ["form_5500_deadlines", "form_5500_due", "register", "report_target_deadlines"]
