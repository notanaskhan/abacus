"""A-05-T10: the EBP-01 service (A-05 §3 F1; SPEC-640; DEC-1955).

The plan's facts (0610 `ebp_plans`, one per EBP work item) and its service providers
(`ebp_service_providers`), with the checks code runs over them (`ebp_provider_checks`,
insert-only). Every plan field a person changes goes through `review.api.record_value` with a
citation note (the field history EBP-01's chips read), and the row carries the new version and
content hash. The plan number lives on the plan entity (`client_entities.plan_number`) and is
written through `organisations.api`; code refuses 000, a non-three-digit value and the
recordkeeper's plan ID with the Form 5500 line 1b helper (422 `plan_number_invalid`).

The filer status and due date are the plan-status engine's (`compute/ebp/plan_status.py`) over
the row and the firm's holiday set. Provider checks, by code: a SOC 1 report whose period ends
before the plan year (`soc_gap`, with the uncovered dates) and a Schedule C EIN ending that
differs from the service agreement's (`ein_mismatch`, routed to the plan's TPA, the Form 5500
preparer). Only last-four digits are taken here; the full EIN and its fingerprint wait for the
PII reveal work (A-05-T18; DEC-1955).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import FetchedValue, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base, TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.assurance.compute.ebp import plan_status as engine
from abacus.modules.engagements.api import assurance_item, lock_ref
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations.api import entity_plan_number, set_entity_plan_number
from abacus.modules.review.api import Json, content_hash, record_value

TARGET: Final = "ebp_plan"
_DATES: Final = frozenset(
    {
        "plan_year_start",
        "plan_year_end",
        "form_5558_filed_on",
        "report_target_on",
        "plan_document_on",
        "opinion_letter_on",
    }
)
_INTS: Final = frozenset({"participants_boy_with_balances", "participants_eoy"})
_TEXT: Final = frozenset({"safe_harbor", "recordkeeper_plan_id", "prior_year_filer", "qdia"})
_TEXT_LONG: Final = frozenset({"latest_amendment_ref"})
_MONEY: Final = frozenset({"fidelity_bond_amount"})
EDITABLE: Final = _DATES | _INTS | _TEXT | _TEXT_LONG | _MONEY | {"plan_number"}
_CHOICES: Final[Mapping[str, frozenset[str]]] = {
    "safe_harbor": frozenset({"none", "qaca", "basic", "nonelective"}),
    "prior_year_filer": frozenset({"large_plan", "small_plan"}),
}


class EbpPlan(Base):
    __tablename__ = "ebp_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    plan_entity_id: Mapped[UUID | None]
    sponsor_entity_id: Mapped[UUID | None]
    plan_year_start: Mapped[date]
    plan_year_end: Mapped[date]
    plan_type: Mapped[str]
    safe_harbor: Mapped[str]
    auto_enrollment: Mapped[dict[str, Any] | None] = mapped_column(  # Any: JSON
        JSONB(none_as_null=True)
    )
    match_formula: Mapped[dict[str, Any] | None] = mapped_column(  # Any: JSON
        JSONB(none_as_null=True)
    )
    qdia: Mapped[str | None]
    recordkeeper_plan_id: Mapped[str | None]
    participants_boy_with_balances: Mapped[int | None]
    participants_eoy: Mapped[int | None]
    prior_year_filer: Mapped[str | None]
    form_5558_filed_on: Mapped[date | None]
    report_target_on: Mapped[date | None]
    fidelity_bond_amount: Mapped[Decimal | None]
    plan_document_on: Mapped[date | None]
    opinion_letter_on: Mapped[date | None]
    latest_amendment_ref: Mapped[str | None]
    version: Mapped[int]
    content_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class EbpProvider(Base):
    __tablename__ = "ebp_service_providers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    org_name: Mapped[str]
    role: Mapped[str]
    contact_id: Mapped[UUID | None]
    grant_id: Mapped[UUID | None]
    tin_last4: Mapped[str | None]  # 0612 renamed ein_* to the platform's tin_* names
    soc_type: Mapped[str | None]
    soc_period_start: Mapped[date | None]
    soc_period_end: Mapped[date | None]
    certifies: Mapped[bool]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class EbpProviderCheck(Base):
    __tablename__ = "ebp_provider_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    check_kind: Mapped[str]
    provider_id: Mapped[UUID | None]
    result: Mapped[str]
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    issue_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


# --- errors --------------------------------------------------------------------------------------


class PlanNumberInvalid(DomainInvalid):
    """Not a Form 5500 plan number (line 1b): three digits 001 to 999, never the recordkeeper's
    plan ID; `facts.reason` and `facts.helper` say which and where to look."""

    code = "plan_number_invalid"


class PlanFieldInvalid(DomainInvalid):
    code = "ebp_plan_field_invalid"


class CitationNoteRequired(DomainInvalid):
    code = "citation_note_required"


class PlanMoved(DomainConflict):
    code = "version_conflict"


class NotAnEbpAudit(DomainConflict):
    code = "not_an_ebp_audit"


# --- reads ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanView:
    plan: EbpPlan
    plan_name: str
    plan_number: str | None
    status: engine.PlanStatus | None
    audit_kind: Literal["103a3c", "full_scope"]


async def _item(tenant: TenantContext, work_item_id: UUID) -> tuple[UUID, bool, bool]:
    """(engagement, is an EBP audit, §103(a)(3)(C))."""
    item = await assurance_item(tenant, work_item_id)
    ebp = item.ebp_plan_kind is not None or item.assurance_type.startswith("ebp")
    return item.engagement_id, ebp, item.limited_scope_103a3c


async def _plan_row(tenant: TenantContext, work_item_id: UUID) -> EbpPlan | None:
    async with tenant_session(tenant) as session:
        return (
            await session.execute(select(EbpPlan).where(EbpPlan.work_item_id == work_item_id))
        ).scalar_one_or_none()


def status_of(plan: EbpPlan, holidays: frozenset[date]) -> engine.PlanStatus | None:
    if plan.participants_boy_with_balances is None:
        return None
    return engine.plan_status(
        plan_year_end=plan.plan_year_end,
        participants_boy_with_balances=plan.participants_boy_with_balances,
        prior_year_filer=cast(engine.Filer | None, plan.prior_year_filer),
        form_5558_filed_on=plan.form_5558_filed_on,
        holidays=holidays,
    )


async def plan_view(
    ctx: AuthContext, work_item_id: UUID, *, plan_name: str, holidays: frozenset[date]
) -> PlanView:
    """`GET …/ebp/plan` (the route authorised `ebp.read` and the flag); 404 `ebp_plan` until a
    person records the plan's facts."""
    _, ebp, limited = await _item(ctx.tenant, work_item_id)
    found = await _plan_row(ctx.tenant, work_item_id)
    if not ebp or found is None:
        raise NotFound("ebp_plan")
    number = (
        await entity_plan_number(ctx.tenant, found.plan_entity_id)
        if found.plan_entity_id is not None
        else None
    )
    return PlanView(
        found,
        plan_name,
        number,
        status_of(found, holidays),
        "103a3c" if limited else "full_scope",
    )


# --- writes --------------------------------------------------------------------------------------


def _typed(key: str, raw: str) -> object:
    text = raw.strip()
    try:
        if key in _DATES:
            return date.fromisoformat(text)
        if key in _INTS:
            value = int(text)
            if value < 0:
                raise ValueError(key)
            return value
        if key in _MONEY:
            amount = Decimal(text)
            if not amount.is_finite() or amount < 0:
                raise ValueError(key)
            return amount.quantize(Decimal("0.01"))
    except (ValueError, InvalidOperation):
        raise PlanFieldInvalid(facts={"field": key}) from None
    if key in _CHOICES and text not in _CHOICES[key]:
        raise PlanFieldInvalid(facts={"field": key})
    limit = 200 if key in _TEXT_LONG or key == "qdia" else 40
    if not text or len(text) > limit:
        raise PlanFieldInvalid(facts={"field": key})
    return text


def _history_value(key: str, value: object) -> dict[str, object]:
    if key in _DATES:
        return {"t": "date", "v": cast(date, value).isoformat()}
    if key in _INTS | _MONEY:
        return {"t": "decimal", "v": str(value)}
    return {"t": "text", "v": str(value)}


def _hash(p: EbpPlan) -> str:
    return content_hash(
        cast(
            Json,
            {
                k: (v.isoformat() if isinstance(v, date) else str(v) if v is not None else None)
                for k, v in (
                    ("plan_year_start", p.plan_year_start),
                    ("plan_year_end", p.plan_year_end),
                    ("plan_type", p.plan_type),
                    ("safe_harbor", p.safe_harbor),
                    ("qdia", p.qdia),
                    ("recordkeeper_plan_id", p.recordkeeper_plan_id),
                    ("participants_boy_with_balances", p.participants_boy_with_balances),
                    ("participants_eoy", p.participants_eoy),
                    ("prior_year_filer", p.prior_year_filer),
                    ("form_5558_filed_on", p.form_5558_filed_on),
                    ("report_target_on", p.report_target_on),
                    ("fidelity_bond_amount", p.fidelity_bond_amount),
                    ("plan_document_on", p.plan_document_on),
                    ("opinion_letter_on", p.opinion_letter_on),
                    ("latest_amendment_ref", p.latest_amendment_ref),
                )
            },
        )
    )


async def _record_check(
    tx: UnitOfWork,
    ctx: AuthContext,
    plan: EbpPlan,
    *,
    kind: str,
    result: Literal["ok", "flag"],
    provider_id: UUID | None = None,
    facts: Mapping[str, object] | None = None,
) -> None:
    check_id = (
        await tx.session.execute(
            insert(EbpProviderCheck)
            .values(
                tenant_id=ctx.tenant_id,
                engagement_id=plan.engagement_id,
                work_item_id=plan.work_item_id,
                check_kind=kind,
                provider_id=provider_id,
                result=result,
                facts=dict(facts or {}),
            )
            .returning(EbpProviderCheck.id)
        )
    ).scalar_one()
    tx.record(
        "ebp_check.recorded",
        target=Target("ebp_provider_check", check_id),
        after=Ref(flagged=1 if result == "flag" else 0),
        scope=Scope(engagement_id=plan.engagement_id, work_item_id=plan.work_item_id),
    )


async def edit_plan(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    fields: Mapping[str, str],
    citation_note: str,
    seen_version: int,
    plan_entity_id: UUID | None,
) -> None:
    """`PATCH …/ebp/plan` (the route authorised `ebp_plan.edit`): the first save records the plan
    (it needs the plan year); later saves name the version they saw."""
    engagement_id, ebp, _ = await _item(ctx.tenant, work_item_id)
    if not ebp:
        raise NotAnEbpAudit
    note = citation_note.strip()
    if not note:
        raise CitationNoteRequired
    unknown = set(fields) - EDITABLE
    if unknown or not fields:
        raise PlanFieldInvalid(facts={"field": sorted(unknown)[0] if unknown else "fields"})
    values = {k: _typed(k, v) for k, v in fields.items() if k != "plan_number"}
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        plan = (
            await tx.session.execute(
                select(EbpPlan).where(EbpPlan.work_item_id == work_item_id).with_for_update()
            )
        ).scalar_one_or_none()
        if plan is None:
            if (
                seen_version != 1
                or "plan_year_start" not in values
                or "plan_year_end" not in values
            ):
                raise PlanFieldInvalid(facts={"field": "plan_year_start"})
            draft = EbpPlan(
                plan_year_start=values["plan_year_start"],
                plan_year_end=values["plan_year_end"],
                plan_type="401k",
                safe_harbor=values.get("safe_harbor", "none"),
            )
            for key, value in values.items():
                setattr(draft, key, value)
            plan_id = (
                await tx.session.execute(
                    insert(EbpPlan)
                    .values(
                        tenant_id=ctx.tenant_id,
                        engagement_id=engagement_id,
                        work_item_id=work_item_id,
                        plan_entity_id=plan_entity_id,
                        plan_type="401k",
                        content_hash=_hash(draft),
                        **{k: v for k, v in values.items()},
                    )
                    .returning(EbpPlan.id)
                )
            ).scalar_one()
            plan = await tx.session.get(EbpPlan, plan_id)
            if plan is None:
                raise NotFound("ebp_plan")
            tx.record(
                "ebp_plan.created",
                target=Target(TARGET, plan.id),
                scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
            )
        else:
            if plan.version != seen_version:
                raise PlanMoved(facts={"current": plan.version})
            if {"plan_year_start", "plan_year_end"} & set(values):
                raise PlanFieldInvalid(facts={"field": "plan_year_start"})  # fixed once recorded
            for key, value in values.items():
                setattr(plan, key, value)
            plan.version += 1
            plan.content_hash = _hash(plan)
        if "plan_number" in fields:
            problem = engine.plan_number_problem(
                fields["plan_number"], recordkeeper_plan_id=plan.recordkeeper_plan_id
            )
            if problem is not None:
                raise PlanNumberInvalid(
                    facts={"reason": problem, "helper": engine.FORM_5500_HELPER}
                )
            if plan.plan_entity_id is None:
                raise PlanFieldInvalid(facts={"field": "plan_entity_id"})
            await set_entity_plan_number(
                tx, ctx, plan.plan_entity_id, fields["plan_number"].strip()
            )
            await _record_check(tx, ctx, plan, kind="pn_format", result="ok")
        for key in sorted(fields):
            value = fields[key].strip() if key == "plan_number" else values[key]
            await record_value(
                tx,
                engagement_id=engagement_id,
                target_type=TARGET,
                target_id=plan.id,
                field_key=key,
                value=_history_value(key, value),
                value_source="human",
                cause="edit",
                citation_note=note,
            )
        tx.record(
            "ebp_plan.edited",
            target=Target(TARGET, plan.id),
            after=Ref(version=plan.version, fields=len(fields)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


# --- providers -----------------------------------------------------------------------------------

ROLES: Final = frozenset(
    {"recordkeeper", "trustee_custodian", "payroll", "tpa", "sdba_broker", "other"}
)


async def providers(tenant: TenantContext, work_item_id: UUID) -> list[EbpProvider]:
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    select(EbpProvider)
                    .where(EbpProvider.work_item_id == work_item_id)
                    .order_by(EbpProvider.created_at, EbpProvider.id)
                )
            ).scalars()
        )


async def checks(tenant: TenantContext, work_item_id: UUID) -> list[EbpProviderCheck]:
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    select(EbpProviderCheck)
                    .where(EbpProviderCheck.work_item_id == work_item_id)
                    .order_by(EbpProviderCheck.created_at, EbpProviderCheck.id)
                )
            ).scalars()
        )


def soc_gap(plan: EbpPlan, provider: EbpProvider) -> tuple[date, date] | None:
    """The plan-year days the provider's SOC 1 report does not cover at its end, by code."""
    if provider.soc_type not in ("soc1_type1", "soc1_type2") or provider.soc_period_end is None:
        return None
    if provider.soc_period_end >= plan.plan_year_end:
        return None
    return provider.soc_period_end + timedelta(days=1), plan.plan_year_end


@dataclass(frozen=True)
class NewProvider:
    org_name: str
    role: str
    soc_type: str | None = None
    soc_period_start: date | None = None
    soc_period_end: date | None = None
    certifies: bool = False
    agreement_ein_last4: str | None = None
    schedule_c_ein_last4: str | None = None


async def add_provider(ctx: AuthContext, work_item_id: UUID, new: NewProvider) -> EbpProvider:
    """`POST …/ebp/providers` (the route authorised `ebp_provider.manage`): the provider and its
    checks (SOC gap; the Schedule C EIN ending against the agreement's, routed to the TPA)."""
    engagement_id, ebp, _ = await _item(ctx.tenant, work_item_id)
    if not ebp:
        raise NotAnEbpAudit
    if new.role not in ROLES or not new.org_name.strip():
        raise PlanFieldInvalid(facts={"field": "role" if new.role not in ROLES else "name"})
    for last4 in (new.agreement_ein_last4, new.schedule_c_ein_last4):
        if last4 is not None and not (len(last4) == 4 and last4.isdigit()):
            raise PlanFieldInvalid(facts={"field": "ein_last4"})
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        plan = (
            await tx.session.execute(select(EbpPlan).where(EbpPlan.work_item_id == work_item_id))
        ).scalar_one_or_none()
        if plan is None:
            raise NotFound("ebp_plan")
        provider_id = (
            await tx.session.execute(
                insert(EbpProvider)
                .values(
                    tenant_id=ctx.tenant_id,
                    engagement_id=engagement_id,
                    work_item_id=work_item_id,
                    org_name=new.org_name.strip(),
                    role=new.role,
                    soc_type=new.soc_type,
                    soc_period_start=new.soc_period_start,
                    soc_period_end=new.soc_period_end,
                    certifies=new.certifies,
                )
                .returning(EbpProvider.id)
            )
        ).scalar_one()
        provider = await tx.session.get(EbpProvider, provider_id)
        if provider is None:
            raise NotFound("ebp_provider")
        tx.record(
            "ebp_provider.created",
            target=Target("ebp_provider", provider_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        gap = soc_gap(plan, provider)
        if gap is not None:
            await _record_check(
                tx,
                ctx,
                plan,
                kind="soc_gap",
                result="flag",
                provider_id=provider_id,
                facts={"uncovered_from": gap[0].isoformat(), "uncovered_to": gap[1].isoformat()},
            )
        if new.agreement_ein_last4 and new.schedule_c_ein_last4:
            same = new.agreement_ein_last4 == new.schedule_c_ein_last4
            tpa = (
                await tx.session.execute(
                    select(EbpProvider.id).where(
                        EbpProvider.work_item_id == work_item_id, EbpProvider.role == "tpa"
                    )
                )
            ).scalar_one_or_none()
            await _record_check(
                tx,
                ctx,
                plan,
                kind="ein_mismatch",
                result="ok" if same else "flag",
                provider_id=provider_id,
                facts={
                    "agreement_last4": new.agreement_ein_last4,
                    "schedule_c_last4": new.schedule_c_ein_last4,
                    "routed_to_provider_id": str(tpa) if tpa else None,
                },
            )
        if gap is not None or (
            new.agreement_ein_last4
            and new.schedule_c_ein_last4
            and new.agreement_ein_last4 != new.schedule_c_ein_last4
        ):
            provider.status = "correction_requested"
    return await _provider(ctx.tenant, work_item_id, provider_id)


async def _provider(tenant: TenantContext, work_item_id: UUID, provider_id: UUID) -> EbpProvider:
    async with tenant_session(tenant) as session:
        found = await session.get(EbpProvider, provider_id)
    if found is None or found.work_item_id != work_item_id:
        raise NotFound("ebp_provider")
    return found


def check_notes(found: Sequence[EbpProviderCheck], names: Mapping[UUID, str]) -> dict[UUID, str]:
    """A provider's latest flagged check as EBP-01's sentence, from code facts only."""
    out: dict[UUID, str] = {}
    for c in found:
        if c.result != "flag" or c.provider_id is None:
            continue
        if c.check_kind == "ein_mismatch":
            routed = c.facts.get("routed_to_provider_id")
            to = names.get(UUID(str(routed))) if routed else None
            out[c.provider_id] = (
                f"Schedule C lists EIN ending {c.facts.get('schedule_c_last4')}; the agreement "
                f"shows {c.facts.get('agreement_last4')}" + (f" · routed to {to}" if to else "")
            )
        elif c.check_kind == "soc_gap":
            out[c.provider_id] = (
                f"SOC 1 does not cover {c.facts.get('uncovered_from')} to "
                f"{c.facts.get('uncovered_to')}"
            )
    return out


async def engagement_of(tenant: TenantContext, work_item_id: UUID) -> UUID:
    return (await _item(tenant, work_item_id))[0]


AUDIT_KINDS = frozenset({TARGET, "ebp_provider", "ebp_provider_check"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For EBP-01's rows named by an audit event: id -> the owning engagement."""
    table = {TARGET: EbpPlan, "ebp_provider": EbpProvider, "ebp_provider_check": EbpProviderCheck}[
        kind
    ]
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(table.id, table.engagement_id).where(table.id.in_(list(ids)))
        )
        return {found: owned for found, owned in rows}
