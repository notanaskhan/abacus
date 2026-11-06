"""A-05-T30: the late-remittance service (A-05 §4.4; EBP-04, EBP-07, AUD-27; DF-34; DEC-2237).

One `ebp_late_remittances` row per late payroll (0658) is **the** late-remittance object: EBP-04 f
draws it, the Schedule H line 4a preview sums its principal, and AUD-27's prohibited-transaction
card and EBP-07's Part IV 4a read it through `assurance.api.late_remittances`, so recording a
correction changes all three together, from one row.

The correction state machine moves only by a person's recorded event with evidence (time alone
never corrects): `found` → `pending_vfcp_scc` once the lost earnings are deposited → `corrected`
once the VFCP SCC notice is given; Form 5330 moves from `exposure` to
`not_required_pte_2002_51` (a VFCP correction under PTE 2002-51) or `filed`. Each move writes an
insert-only `ebp_late_remittance_events` row (human, 0658's CHECK) and an audit event. Figures are
code's (`compute.ebp.remittance`); the routes have authorised the action and the flag.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import FetchedValue, insert, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.clock import now
from abacus.kernel.db import Base, TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance.compute.ebp import remittance
from abacus.modules.identity.api import AuthContext

FORM_5330: Final = {"not_required": "not_required_pte_2002_51", "filed": "filed"}


class EbpPayroll(Base):
    __tablename__ = "ebp_payrolls"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    pay_date: Mapped[date]
    deferrals_pretax: Mapped[Decimal]
    deferrals_roth: Mapped[Decimal]
    match: Mapped[Decimal]
    deposit_date: Mapped[date | None]
    business_day_lag: Mapped[int | None]
    calendar_lag: Mapped[int | None]
    result: Mapped[str | None]


class EbpLateRemittance(Base):
    __tablename__ = "ebp_late_remittances"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    payroll_id: Mapped[UUID]
    principal: Mapped[Decimal]
    due_on: Mapped[date]
    deposited_on: Mapped[date | None]
    business_days_late: Mapped[int]
    interest_days: Mapped[int | None]
    lost_earnings: Mapped[Decimal | None]
    excise_exposure: Mapped[Decimal | None]
    correction_status: Mapped[str] = mapped_column(server_default=FetchedValue())
    lost_earnings_deposited_on: Mapped[date | None]
    scc_notice_on: Mapped[date | None]
    form_5330_status: Mapped[str] = mapped_column(server_default=FetchedValue())
    schedule_h_4a: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    finding_id: Mapped[UUID | None]
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class EbpLateRemittanceEvent(Base):
    __tablename__ = "ebp_late_remittance_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    late_remittance_id: Mapped[UUID]
    event: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    evidence_version_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    actor_kind: Mapped[str]
    actor_user_id: Mapped[UUID | None]


class CorrectionEvidenceRequired(DomainInvalid):
    """A correction is recorded with the evidence that shows it (deposit, SCC notice)."""

    code = "correction_evidence_required"


class AlreadyCorrected(DomainConflict):
    """The late remittance is corrected; a later fact is a new event, not a correction."""

    code = "already_corrected"


@dataclass(frozen=True)
class LateRemittance:
    """What EBP-04 f, the 4a preview, AUD-27 and EBP-07 read (identifiers and code's figures)."""

    id: UUID
    payroll_date: date
    deposited_on: date | None
    principal: Decimal
    business_days: int
    business_days_late: int
    calendar_days: int
    lost_earnings: Decimal | None
    excise_exposure: Decimal | None
    status: str
    form_5330: str  # the API word: exposure, not_required, filed
    finding_id: UUID | None
    version: int


def _api_form_5330(stored: str) -> str:
    return "not_required" if stored == "not_required_pte_2002_51" else stored


@dataclass(frozen=True)
class Payroll:
    id: UUID
    pay_date: date
    deposit_date: date | None
    deferrals_pretax: Decimal
    deferrals_roth: Decimal
    match: Decimal
    deferrals: Decimal
    total: Decimal
    business_day_lag: int | None
    calendar_lag: int | None
    late: bool


async def payrolls(tenant: TenantContext, work_item_id: UUID) -> list[Payroll]:
    """The work item's payrolls, oldest first; late when a late remittance names the payroll."""
    async with tenant_session(tenant) as session:
        late_ids = set(
            (
                await session.execute(
                    select(EbpLateRemittance.payroll_id).where(
                        EbpLateRemittance.work_item_id == work_item_id
                    )
                )
            ).scalars()
        )
        rows = (
            await session.execute(
                select(EbpPayroll)
                .where(EbpPayroll.work_item_id == work_item_id)
                .order_by(EbpPayroll.pay_date)
            )
        ).scalars()
        return [
            Payroll(
                id=p.id,
                pay_date=p.pay_date,
                deposit_date=p.deposit_date,
                deferrals_pretax=p.deferrals_pretax,
                deferrals_roth=p.deferrals_roth,
                match=p.match,
                deferrals=p.deferrals_pretax + p.deferrals_roth,
                total=p.deferrals_pretax + p.deferrals_roth + p.match,
                business_day_lag=p.business_day_lag,
                calendar_lag=p.calendar_lag,
                late=p.id in late_ids,
            )
            for p in rows
        ]


async def late_remittances(tenant: TenantContext, work_item_id: UUID) -> list[LateRemittance]:
    """`assurance.api.late_remittances`: every late payroll on the work item, oldest first."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(EbpLateRemittance, EbpPayroll)
            .join(EbpPayroll, EbpPayroll.id == EbpLateRemittance.payroll_id)
            .where(EbpLateRemittance.work_item_id == work_item_id)
            .order_by(EbpPayroll.pay_date)
        )
        return [
            LateRemittance(
                id=late.id,
                payroll_date=payroll.pay_date,
                deposited_on=late.deposited_on,
                principal=late.principal,
                business_days=payroll.business_day_lag or late.business_days_late,
                business_days_late=late.business_days_late,
                calendar_days=payroll.calendar_lag or 0,
                lost_earnings=late.lost_earnings,
                excise_exposure=late.excise_exposure,
                status=late.correction_status,
                form_5330=_api_form_5330(late.form_5330_status),
                finding_id=late.finding_id,
                version=late.version,
            )
            for late, payroll in rows
        ]


def schedule_h_4a(rows: Sequence[LateRemittance]) -> Decimal:
    """Line 4a from the late remittances' principal (deferrals only; code's sum)."""
    return remittance.schedule_h_4a([r.principal for r in rows])


async def record_correction(
    ctx: AuthContext,
    work_item_id: UUID,
    remittance_id: UUID,
    *,
    lost_earnings_deposited_on: date,
    scc_notice_on: date | None,
    form_5330_status: str,
    evidence_version_ids: Sequence[UUID],
) -> UUID:
    """A person records the correction with its evidence (EBP-04 f): `pending_vfcp_scc` until the
    SCC notice, then `corrected`; Form 5330 as recorded. One event row, one audit event."""
    if not evidence_version_ids:
        raise CorrectionEvidenceRequired
    if form_5330_status not in FORM_5330:
        raise DomainInvalid("form_5330_status")
    async with uow(ctx.tenant) as tx:
        late = (
            await tx.session.execute(
                select(EbpLateRemittance)
                .where(
                    EbpLateRemittance.id == remittance_id,
                    EbpLateRemittance.work_item_id == work_item_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if late is None:
            raise NotFound("late_remittance")
        if late.correction_status == "corrected":
            raise AlreadyCorrected
        if late.deposited_on and lost_earnings_deposited_on < late.deposited_on:
            raise DomainInvalid("lost_earnings_deposited_on")
        late.lost_earnings_deposited_on = lost_earnings_deposited_on
        late.scc_notice_on = scc_notice_on
        late.correction_status = "corrected" if scc_notice_on else "pending_vfcp_scc"
        late.form_5330_status = FORM_5330[form_5330_status]
        late.version += 1
        late.updated_at = await now(ctx.tenant)
        event_id = (
            await tx.session.execute(
                insert(EbpLateRemittanceEvent)
                .values(
                    tenant_id=ctx.tenant_id,
                    engagement_id=late.engagement_id,
                    work_item_id=work_item_id,
                    late_remittance_id=remittance_id,
                    event="correction_recorded",
                    payload={
                        "lost_earnings_deposited_on": lost_earnings_deposited_on.isoformat(),
                        "scc_notice_on": scc_notice_on.isoformat() if scc_notice_on else None,
                        "form_5330_status": late.form_5330_status,
                        "correction_status": late.correction_status,
                    },
                    evidence_version_ids=list(evidence_version_ids),
                    actor_kind="human",
                    actor_user_id=ctx.user_id,
                )
                .returning(EbpLateRemittanceEvent.id)
            )
        ).scalar_one()
        tx.record(
            "ebp_late_remittance.correction_recorded",
            target=Target("ebp_late_remittance", remittance_id),
            after=Ref(event=event_id, version=late.version),
            scope=Scope(engagement_id=late.engagement_id, work_item_id=work_item_id),
        )
    return event_id


@dataclass(frozen=True)
class Reconciliation:
    regular: Decimal
    late: Decimal
    total: Decimal
    deferrals: Decimal = Decimal(0)
    match: Decimal = Decimal(0)
    trust_receipts: Decimal = Decimal(0)


async def reconciliation(
    tenant: TenantContext, work_item_id: UUID, year_end: date
) -> Reconciliation:
    """A-05-T31's waterfall (DEC-2356): the plan year's payroll and match, less what was deposited
    after year end, is the trust's receipts for them. Receivable at year end by code: payrolls of
    the plan year deposited after it,
    split into regular and late (the late remittance's payroll)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(EbpPayroll).where(
                    EbpPayroll.work_item_id == work_item_id,
                    EbpPayroll.pay_date <= year_end,
                    EbpPayroll.pay_date >= date(year_end.year, 1, 1),
                )
            )
        ).scalars()
        late_ids = set(
            (
                await session.execute(
                    select(EbpLateRemittance.payroll_id).where(
                        EbpLateRemittance.work_item_id == work_item_id
                    )
                )
            ).scalars()
        )
    regular = late = deferrals = match = Decimal(0)
    for p in rows:
        amount = p.deferrals_pretax + p.deferrals_roth + p.match
        deferrals += p.deferrals_pretax + p.deferrals_roth
        match += p.match
        if p.deposit_date is None or p.deposit_date <= year_end:
            continue
        if p.id in late_ids:
            late += amount
        else:
            regular += amount
    total = regular + late
    return Reconciliation(regular, late, total, deferrals, match, deferrals + match - total)


AUDIT_KINDS = frozenset({"ebp_late_remittance"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `ebp_late_remittance` rows named by an audit event: id -> the owning engagement."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(EbpLateRemittance.id, EbpLateRemittance.engagement_id).where(
                EbpLateRemittance.id.in_(list(ids))
            )
        )
        return {found: owned for found, owned in rows}
