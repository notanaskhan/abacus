"""A-04-T31: SOC 1 report evaluation (A-04 AC7.1 to AC7.6; AUD-10; DEC-2236).

A SOC report evaluation (0657's `soc_report_evaluations`) belongs to one service organization on
the audit work item. A person records the report's facts (service auditor, opinion, type, period,
objectives) against the version they saw; code recomputes the gap against the plan year
(`compute/soc_gap.py`) and stores it with its engine stamp. CUECs map to a control activity and
the evidence that shows it operated; one is Evidenced only with evidence. SOC exceptions carry a
person's impact. Bridge-letter and CUEC-evidence requests are C5 **drafts** a person sends.

Reliance is the engagement partner's `service_org_reliance` card (DEC-83): raising it answers
409 `gap_open` while an unbridged gap stands and 409 `cuec_evidence_missing` while any relevant
CUEC lacks evidence; the agent never raises or decides it. Deciding it sets the reliance state in
the decider's unit of work and emits `service_org.reliance_concluded` (identifiers only).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import FetchedValue, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.clock import now
from abacus.kernel.db import Base, TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.assurance.compute import soc_gap
from abacus.modules.assurance.events import ServiceOrgRelianceConcluded
from abacus.modules.assurance.internal_control import (
    AlreadyRouted,
    RouteNotAvailable,
    RouteRequest,
    exception_router,
)
from abacus.modules.engagements.api import assurance_item_id, engagement_metadata
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import (
    AppliedDecision,
    CardContext,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    raise_decision_card,
    register_decision_kind,
)

RELIANCE_KIND: Final = "service_org_reliance"
RELY: Final = "rely"
NOT_RELY: Final = "do_not_rely"


class SocReportEvaluation(Base):
    __tablename__ = "soc_report_evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    service_organization_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    service_auditor_name: Mapped[str | None]
    opinion: Mapped[str | None]
    report_type: Mapped[str | None]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    report_date: Mapped[date | None]
    objectives_total: Mapped[int | None]
    objectives_relevant: Mapped[int | None]
    bridge_letter_request_item_id: Mapped[UUID | None]
    bridge_letter_evidence_version_id: Mapped[UUID | None]
    gap_days: Mapped[int | None]
    engine_version: Mapped[str | None]
    inputs_hash: Mapped[str | None]
    reliance_state: Mapped[str] = mapped_column(server_default=FetchedValue())
    reliance_card_id: Mapped[UUID | None]
    row_version: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class SocException(Base):
    __tablename__ = "soc_exceptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    evaluation_id: Mapped[UUID]
    co_ref: Mapped[str]
    description: Mapped[str]
    impact: Mapped[str | None]
    impact_rationale: Mapped[str | None]
    routed_ref: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Cuec(Base):
    __tablename__ = "cuecs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    evaluation_id: Mapped[UUID]
    n: Mapped[int]
    text: Mapped[str]
    control_activity_id: Mapped[UUID | None]
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(  # Any: JSON
        JSONB, server_default=FetchedValue()
    )
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    page_citation_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class SocReportMoved(DomainConflict):
    """The evaluation changed since the caller read it."""

    code = "version_conflict"


class GapOpen(DomainConflict):
    """The report leaves plan-year days uncovered and no bridge letter is in hand."""

    code = "gap_open"


class CuecEvidenceMissing(DomainConflict):
    """A CUEC has no evidence that the user control operated."""

    code = "cuec_evidence_missing"


class RelianceRequested(DomainConflict):
    """The engagement partner's reliance card is already raised or decided."""

    code = "reliance_requested"


class NoCuecs(DomainInvalid):
    """CUEC evidence requests name at least one CUEC of this report."""

    code = "cuecs_required"


@dataclass(frozen=True)
class SocReport:
    row: SocReportEvaluation
    gap: soc_gap.Gap | None
    exceptions: tuple[SocException, ...]
    cuecs: tuple[Cuec, ...]

    @property
    def cuecs_evidenced(self) -> int:
        return sum(1 for c in self.cuecs if c.status == "evidenced")


async def _work_item(tenant: TenantContext, engagement_id: UUID) -> UUID:
    found = await assurance_item_id(tenant, engagement_id)
    if found is None:
        raise NotFound("soc_report")
    return found


async def _plan_year(ctx: AuthContext, engagement_id: UUID) -> tuple[date, date]:
    period = (await engagement_metadata(ctx, engagement_id)).engagement
    return period.fiscal_period_start, period.fiscal_period_end


def _gap(row: SocReportEvaluation, plan_year: tuple[date, date]) -> soc_gap.Gap | None:
    if row.period_start is None or row.period_end is None:
        return None
    return soc_gap.gap(
        plan_year_start=plan_year[0],
        plan_year_end=plan_year[1],
        period_start=row.period_start,
        period_end=row.period_end,
        bridge_received=row.bridge_letter_evidence_version_id is not None,
    )


async def _load(tenant: TenantContext, work_item: UUID, report_id: UUID) -> SocReport:
    async with tenant_session(tenant) as session:
        row = await session.get(SocReportEvaluation, report_id)
        if row is None or row.work_item_id != work_item:
            raise NotFound("soc_report")
        exceptions = (
            await session.execute(
                select(SocException)
                .where(SocException.evaluation_id == report_id)
                .order_by(SocException.co_ref)
            )
        ).scalars()
        cuecs = (
            await session.execute(
                select(Cuec).where(Cuec.evaluation_id == report_id).order_by(Cuec.n)
            )
        ).scalars()
        return SocReport(row, None, tuple(exceptions), tuple(cuecs))


async def report(ctx: AuthContext, engagement_id: UUID, report_id: UUID) -> SocReport:
    """The evaluation with its gap recomputed live from the plan year (AC7.1)."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    found = await _load(ctx.tenant, work_item, report_id)
    return SocReport(
        found.row,
        _gap(found.row, await _plan_year(ctx, engagement_id)),
        found.exceptions,
        found.cuecs,
    )


async def _locked(
    tx: UnitOfWork, work_item: UUID, report_id: UUID, expected: int
) -> SocReportEvaluation:
    row = (
        await tx.session.execute(
            select(SocReportEvaluation)
            .where(
                SocReportEvaluation.id == report_id, SocReportEvaluation.work_item_id == work_item
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("soc_report")
    if row.row_version != expected:
        raise SocReportMoved(facts={"current": row.row_version})
    return row


async def evaluate(
    ctx: AuthContext,
    engagement_id: UUID,
    report_id: UUID,
    *,
    expected_version: int,
    report_type: str | None = None,
    opinion: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    report_date: date | None = None,
    bridge_letter_evidence_version_id: UUID | None = None,
) -> SocReport:
    """Record the report's facts; code recomputes and stores the gap with its stamp (AC7.6)."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    plan_year = await _plan_year(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, work_item, report_id, expected_version)
        if row.reliance_state != "pending":
            raise RelianceRequested(facts={"reliance_state": row.reliance_state})
        for name, value in (
            ("report_type", report_type),
            ("opinion", opinion),
            ("period_start", period_start),
            ("period_end", period_end),
            ("report_date", report_date),
            ("bridge_letter_evidence_version_id", bridge_letter_evidence_version_id),
        ):
            if value is not None:
                setattr(row, name, value)
        computed = _gap(row, plan_year)
        if computed is not None:
            row.gap_days = computed.days
            row.engine_version = computed.stamp.engine_version
            row.inputs_hash = computed.stamp.inputs_hash
        row.row_version += 1
        row.updated_at = await now(ctx.tenant)
        tx.record(
            "soc_report.evaluated",
            target=Target("soc_report_evaluation", report_id),
            after=Ref(row_version=row.row_version, gap_days=row.gap_days or 0),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await report(ctx, engagement_id, report_id)


class ExceptionNotHigh(DomainConflict):
    """AC7.5: only a High-impact exception routes to Findings."""

    code = "exception_not_high"


async def _exception(tx: UnitOfWork, report: SocReportEvaluation, co_ref: str) -> SocException:
    found = await tx.session.scalar(
        select(SocException)
        .where(SocException.evaluation_id == report.id, SocException.co_ref == co_ref)
        .with_for_update()
    )
    if found is None:
        raise NotFound("soc_exception")
    return found


async def set_exception_impact(
    ctx: AuthContext,
    engagement_id: UUID,
    report_id: UUID,
    co_ref: str,
    impact: str,
    rationale: str | None,
) -> SocReport:
    """A person's adopted impact. A routed exception keeps the impact it was routed on."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        report_row = await tx.session.scalar(
            select(SocReportEvaluation).where(
                SocReportEvaluation.id == report_id,
                SocReportEvaluation.work_item_id == work_item,
            )
        )
        if report_row is None:
            raise NotFound("soc_report")
        row = await _exception(tx, report_row, co_ref)
        if row.routed_ref is not None:
            raise AlreadyRouted(facts={"routed_ref": str(row.routed_ref)})
        row.impact = impact
        row.impact_rationale = rationale
        row.updated_at = await now(ctx.tenant)
        tx.record(
            "soc_exception.impact_recorded",
            target=Target("soc_report_evaluation", report_id),
            after=Ref(high=int(impact == "high")),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await report(ctx, engagement_id, report_id)


async def route_exception(
    ctx: AuthContext, engagement_id: UUID, report_id: UUID, co_ref: str
) -> SocReport:
    """AC7.5: through A-06's router, in one unit of work with the row's reference."""
    router = exception_router("finding")
    if router is None:
        raise RouteNotAvailable
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        report_row = await tx.session.scalar(
            select(SocReportEvaluation).where(
                SocReportEvaluation.id == report_id,
                SocReportEvaluation.work_item_id == work_item,
            )
        )
        if report_row is None:
            raise NotFound("soc_report")
        row = await _exception(tx, report_row, co_ref)
        if row.routed_ref is not None:
            raise AlreadyRouted(facts={"routed_ref": str(row.routed_ref)})
        if row.impact != "high":
            raise ExceptionNotHigh(facts={"impact": row.impact or ""})
        row.routed_ref = await router(
            tx,
            RouteRequest(
                engagement_id=engagement_id,
                work_item_id=work_item,
                control_exception_id=row.id,
                address=row.co_ref,
                matter=row.description[:300],
                description=row.description,
                proposed_severity=None,
                coso_component=None,
                amount=None,
                citation_ids=(),
                requested_by=ctx.user_id,
            ),
        )
        row.updated_at = await now(ctx.tenant)
        tx.record(
            "soc_exception.routed",
            target=Target("soc_report_evaluation", report_id),
            after=Ref(routed=int(row.routed_ref is not None)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await report(ctx, engagement_id, report_id)


async def map_cuec(
    ctx: AuthContext,
    engagement_id: UUID,
    report_id: UUID,
    n: int,
    *,
    expected_version: int,
    control_activity_id: UUID | None,
    evidence_version_ids: Sequence[UUID],
) -> SocReport:
    """Map CUEC n to a control activity and its evidence; Evidenced only with evidence (AC7.3)."""
    work_item = await _work_item(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, work_item, report_id, expected_version)
        cuec = (
            await tx.session.execute(
                select(Cuec).where(Cuec.evaluation_id == report_id, Cuec.n == n).with_for_update()
            )
        ).scalar_one_or_none()
        if cuec is None:
            raise NotFound("cuec")
        cuec.control_activity_id = control_activity_id
        cuec.evidence_refs = [{"evidence_version_id": str(v)} for v in evidence_version_ids]
        cuec.status = "evidenced" if evidence_version_ids else "evidence_missing"
        cuec.updated_at = await now(ctx.tenant)
        row.row_version += 1
        row.updated_at = cuec.updated_at
        tx.record(
            "soc_report.cuec_mapped",
            target=Target("soc_report_evaluation", report_id),
            after=Ref(n=n, evidence=len(evidence_version_ids)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    return await report(ctx, engagement_id, report_id)


async def request_drafts(
    ctx: AuthContext, engagement_id: UUID, report_id: UUID, *, kind: str, cuec_ns: Sequence[int]
) -> list[UUID]:
    """C5 request **drafts** (AC7.4): the bridge letter to the service organization's contact
    (POR-14) or CUEC evidence from the client (POR-03). A person reviews and sends them."""
    from abacus.modules.requests.api import NewRequestItem, add_request_item

    found = await report(ctx, engagement_id, report_id)
    if kind == "bridge_letter":
        through = found.gap.end.isoformat() if found.gap and found.gap.end else "year end"
        item = await add_request_item(
            ctx,
            engagement_id,
            NewRequestItem(
                description=(
                    f"Bridge letter covering the period after the SOC 1 report through {through}"
                ),
                audit_area="service_organizations",
            ),
        )
        async with uow(ctx.tenant) as tx:
            row = await tx.session.get(SocReportEvaluation, report_id, with_for_update=True)
            if row is None:
                raise NotFound("soc_report")
            row.bridge_letter_request_item_id = item.id
            row.updated_at = await now(ctx.tenant)
            tx.record(
                "soc_report.bridge_letter_drafted",
                target=Target("soc_report_evaluation", report_id),
                after=Ref(request_item_id=item.id),
            )
        return [item.id]
    wanted = [c for c in found.cuecs if c.n in set(cuec_ns)]
    if not wanted:
        raise NoCuecs
    ids: list[UUID] = []
    for cuec in wanted:
        item = await add_request_item(
            ctx,
            engagement_id,
            NewRequestItem(
                description=f"Evidence that CUEC {cuec.n} operated during the plan year",
                audit_area="service_organizations",
            ),
        )
        ids.append(item.id)
    return ids


def _blocking(found: SocReport) -> SocReportMoved | GapOpen | CuecEvidenceMissing | None:
    if found.gap is not None and found.gap.days > 0 and not found.gap.bridged:
        return GapOpen(facts={"gap_days": found.gap.days})
    missing = [c.n for c in found.cuecs if c.status != "evidenced"]
    if missing:
        return CuecEvidenceMissing(facts={"cuecs": len(missing)})
    return None


async def request_reliance(ctx: AuthContext, engagement_id: UUID, report_id: UUID) -> UUID:
    """Raise the EP's `service_org_reliance` card (AC7.2): 409 `gap_open` while the gap is
    unbridged, 409 `cuec_evidence_missing` while any CUEC lacks evidence."""
    found = await report(ctx, engagement_id, report_id)
    if found.row.reliance_card_id is not None or found.row.reliance_state != "pending":
        raise RelianceRequested(facts={"reliance_state": found.row.reliance_state})
    blocked = _blocking(found)
    if blocked is not None:
        raise blocked
    card_id = await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=RELIANCE_KIND,
        question_key=f"soc.{report_id.hex}",
        work_item_id=found.row.work_item_id,
    )
    async with uow(ctx.tenant) as tx:
        row = await tx.session.get(SocReportEvaluation, report_id, with_for_update=True)
        if row is None:
            raise NotFound("soc_report")
        row.reliance_card_id = card_id
        row.updated_at = await now(ctx.tenant)
        tx.record(
            "soc_report.reliance_requested",
            target=Target("soc_report_evaluation", report_id),
            after=Ref(card=card_id),
        )
    return card_id


def _report_id(question_key: str) -> UUID:
    return UUID(hex=question_key.removeprefix("soc."))


async def _reliance_card(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The `service_org_reliance` provider: Rely or Do not rely, over the evaluation as code
    computed it (gap, CUECs evidenced, version)."""
    report_id = _report_id(subject.question_key)
    async with tenant_session(tenant) as session:
        row = await session.get(SocReportEvaluation, report_id)
        cuecs = list(
            (await session.execute(select(Cuec).where(Cuec.evaluation_id == report_id))).scalars()
        )
    if row is None:
        raise NotFound("soc_report")
    figures = {
        "row_version": str(row.row_version),
        "gap_days": str(row.gap_days or 0),
        "cuecs_evidenced": str(sum(1 for c in cuecs if c.status == "evidenced")),
        "cuecs_total": str(len(cuecs)),
    }
    return ComputedCard(
        options=(
            CardOption(RELY, "Rely on the SOC 1 report", figures),
            CardOption(NOT_RELY, "Do not rely; test controls directly", figures),
        ),
        context=(CardContext(f"soc.{report_id.hex}", "SOC 1", row.service_auditor_name or ""),),
    )


async def _apply_reliance(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    """The applier, in the decider's unit of work: the evaluation must be as the card saw it."""
    report_id = _report_id(decided.question_key)
    row = await tx.session.get(SocReportEvaluation, report_id, with_for_update=True)
    if row is None:
        raise NotFound("soc_report")
    if str(row.row_version) != decided.figures.get("row_version"):
        raise SocReportMoved(facts={"current": row.row_version})
    row.reliance_state = "relied" if decided.option_key == RELY else "not_relied"
    row.row_version += 1
    row.updated_at = await now(ctx.tenant)
    tx.record(
        "service_org.reliance_concluded",
        target=Target("soc_report_evaluation", report_id),
        after=Ref(decision=decided.decision_id, relied=int(row.reliance_state == "relied")),
        scope=Scope(engagement_id=decided.engagement_id, work_item_id=row.work_item_id),
    )
    tx.emit(
        ServiceOrgRelianceConcluded(
            engagement_id=decided.engagement_id,
            work_item_id=row.work_item_id,
            soc_report_id=report_id,
            service_organization_id=row.service_organization_id,
            decision_id=decided.decision_id,
            relied=row.reliance_state == "relied",
        )
    )


def register_reliance_kind() -> None:
    register_decision_kind(
        DecisionKind(
            code=RELIANCE_KIND,
            reserved_role="engagement_partner",
            options=_reliance_card,
            questions={"soc": "Reliance on a SOC 1 report"},
            apply=_apply_reliance,
        )
    )


AUDIT_KINDS = frozenset({"soc_report_evaluation"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `soc_report_evaluation` rows named by an audit event: id -> the owning engagement."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(SocReportEvaluation.id, SocReportEvaluation.engagement_id).where(
                SocReportEvaluation.id.in_(list(ids))
            )
        )
        return {found: owned for found, owned in rows}
