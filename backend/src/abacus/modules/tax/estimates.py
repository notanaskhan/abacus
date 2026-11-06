"""T-03-T07: estimated-tax schedules and the payments union (TAX-13 b; T-03 §3 F5; DF-08;
DEC-2350).

- **Rows.** A schedule is visible when its client is (`visible_clients`, walls applied); the counts
  `{due, paid, scheduled, confirmation_requested, not_required}` come from the viewer's rows for
  the chosen quarter, so a walled client is neither shown nor counted.
- **Inputs.** A person enters the method, the prior-year tax and its source, the threshold flag and
  projected withholding; code recomputes the annual payment and the installments with its stamp
  (`tax.compute.payments`, ADR-050). A year without a parameter file computes nothing.
- **Installments.** A recorded date moves the status: `paid_on` to Paid (with the evidence it rests
  on), `scheduled_for` to Scheduled. No route stores or initiates a payment (DEC-89).
- **Confirmation requests** go in the basis return's engagement binder. A schedule without a basis
  return refuses (409 `no_basis_return`): the "{year} estimated payments" binder part needs a
  work item, and P-06's parts hang off one (recorded in DEC-2350).
- **Follow-ups** draft from the approved Reminder template; a person sends them (DEC-74).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final, cast
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import column, select, table, text

from abacus.kernel.classification import classified
from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import function_holders, work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    firm_tenant_ids,
    may_read_unmasked,
    offshore_consented,
    visible_clients,
)
from abacus.modules.organisations.api import client_name_column
from abacus.modules.tax.compute import payments as engine
from abacus.modules.tax.extensions import (
    ConfirmationSent,
    on_return,
    readable_returns,
    send_confirmation,
)

READ: Final = "estimate_schedule.read"
UPDATE: Final = "estimate_schedule.update"
SEND: Final = "estimate_schedule.confirmation_send"
DUE_SOON_DAYS: Final = 7
_ENTITIES: Final = table("client_entities", column("id"), column("client_id"))
_NOT_REQUIRED: Final = ("not_required_withholding", "not_required_estate_first_years", "prospect")


class EstimateMoved(DomainConflict):
    code = "version_conflict"


class NoBasisReturn(DomainConflict):
    """A confirmation request lives in a binder, which hangs off the basis return's engagement."""

    code = "no_basis_return"


class PaidNeedsEvidence(DomainInvalid):
    """A paid installment rests on the client's evidence (T-03 US-5.3)."""

    code = "paid_needs_evidence"


class PriorTaxNeedsSource(DomainInvalid):
    code = "prior_year_tax_source_required"


class EstimateDueSoon(DomainEvent):
    """An installment falls due soon and is not yet confirmed (identifiers only)."""

    event_type: ClassVar[str] = "estimate.due_soon"

    schedule_id: Annotated[UUID, classified("internal")]
    quarter: Annotated[int, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


@dataclass
class ScheduleRow:
    schedule: dict[str, Any]  # Any: a database row
    client_name: str
    installments: list[dict[str, Any]] = field(  # Any: database rows
        default_factory=list[dict[str, Any]]  # Any: database rows
    )

    def installment(self, quarter: int | None) -> dict[str, Any] | None:  # Any: a database row
        return next((i for i in self.installments if i["quarter"] == quarter), None)


def money(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def counts(rows: Sequence[ScheduleRow], quarter: int) -> dict[str, int]:
    """The chosen quarter's tallies; `due` is the rows that owe something that quarter."""
    statuses = [i["status"] for r in rows if (i := r.installment(quarter)) is not None]
    return {
        "due": sum(1 for s in statuses if s != "not_required"),
        "paid": statuses.count("paid"),
        "scheduled": statuses.count("scheduled"),
        "confirmation_requested": statuses.count("confirmation_requested"),
        "not_required": statuses.count("not_required"),
    }


async def current_quarter(tenant: TenantContext, found: Sequence[ScheduleRow]) -> int:
    """The quarter of the next installment due (TAX-13 b opens on it), else the last."""
    on = await today(tenant)
    upcoming = [i["quarter"] for r in found for i in r.installments if i["due_on"] >= on]
    return min(upcoming) if upcoming else 4


def on_tile(row: ScheduleRow, quarter: int, tile: str | None) -> bool:
    if tile is None:
        return True
    found = row.installment(quarter)
    if found is None:
        return False
    return found["status"] != "not_required" if tile == "due" else found["status"] == tile


async def rows(ctx: AuthContext, tax_year: int) -> list[ScheduleRow]:
    allowed = await visible_clients(ctx, READ, _ENTITIES.c.client_id)
    async with tenant_session(ctx.tenant) as session:
        visible = (
            await session.execute(
                select(
                    _ENTITIES.c.id, client_name_column(_ENTITIES.c.id), _ENTITIES.c.client_id
                ).where(allowed)
            )
        ).all()
        readable = await may_read_unmasked(ctx)
        names: dict[UUID, str] = {
            row[0]: row[1] or ""
            for row in visible
            # Amounts are TRI: an offshore reader needs the client's consent (DEC-52).
            if readable or await offshore_consented(ctx.tenant, row[2])
        }
        if not names:
            return []
        found = (
            await session.execute(
                text(
                    "SELECT * FROM estimate_schedules WHERE tax_year = :y "
                    "AND client_entity_id = ANY(:ids) ORDER BY client_entity_id, jurisdiction"
                ),
                {"y": tax_year, "ids": list(names)},
            )
        ).mappings()
        out = {s["id"]: ScheduleRow(dict(s), names[s["client_entity_id"]]) for s in found}
        if out:
            installments = await session.execute(
                text(
                    "SELECT * FROM estimate_installments WHERE schedule_id = ANY(:ids) "
                    "ORDER BY schedule_id, quarter"
                ),
                {"ids": list(out)},
            )
            for i in installments.mappings():
                out[i["schedule_id"]].installments.append(dict(i))
    return sorted(out.values(), key=lambda r: r.client_name.lower())


async def row_of(ctx: AuthContext, schedule_id: UUID) -> ScheduleRow:
    async with tenant_session(ctx.tenant) as session:
        tax_year = (
            await session.execute(
                text("SELECT tax_year FROM estimate_schedules WHERE id = :id"), {"id": schedule_id}
            )
        ).scalar()
    if tax_year is None:
        raise NotFound("estimate_schedule")
    for row in await rows(ctx, int(tax_year)):
        if row.schedule["id"] == schedule_id:
            return row
    raise NotFound("estimate_schedule")


def _computed(
    method: str,
    tax_year: int,
    prior_year_tax: Decimal | None,
    projected_withholding: Decimal | None,
) -> tuple[Decimal | None, str | None, str | None, tuple[Decimal, ...]]:
    """The annual payment, its stamp and the four amounts, or nothing: a not-required method, a
    year with no parameter file, or a method still missing its tax figure."""
    if method in _NOT_REQUIRED:
        return None, None, None, ()
    try:
        params = engine.parameters(tax_year)
    except LookupError:
        return None, None, None, ()
    if prior_year_tax is None:
        return None, None, None, ()
    annual = engine.required_annual_payment(
        cast(engine.Method, method),
        prior_year_tax=prior_year_tax,
        projected_withholding=projected_withholding,
        params=params,
    )
    if annual.annual is None:
        return None, None, None, ()
    shares = engine.installment_amounts(annual.annual, params)
    return annual.annual, annual.stamp.engine_version, annual.stamp.inputs_hash, shares.amounts


async def _recompute(tx: UnitOfWork, schedule: Mapping[str, Any]) -> None:  # Any: a database row
    """Writes the schedule's computed columns and the unrecorded installments' amounts. A paid or
    scheduled quarter keeps its status; `not_required` follows the method."""
    method = str(schedule["method"])
    annual, version, inputs_hash, shares = _computed(
        method,
        int(schedule["tax_year"]),
        money(schedule["prior_year_tax"]),
        money(schedule["projected_withholding"]),
    )
    await tx.session.execute(
        text(
            "UPDATE estimate_schedules SET annual_required = :a, engine_version = :v, "
            "inputs_hash = :h WHERE id = :id"
        ),
        {"a": annual, "v": version, "h": inputs_hash, "id": schedule["id"]},
    )
    required = method not in _NOT_REQUIRED
    for quarter in (1, 2, 3, 4):
        amount = shares[quarter - 1] if len(shares) >= quarter else None
        await tx.session.execute(
            text(
                "UPDATE estimate_installments SET amount = :amount, status = CASE "
                "WHEN status IN ('paid', 'scheduled') THEN status "
                "WHEN NOT :required THEN 'not_required' "
                "WHEN status = 'not_required' THEN 'not_confirmed' ELSE status END, "
                "row_version = row_version + 1 WHERE schedule_id = :s AND quarter = :q"
            ),
            {"amount": amount, "required": required, "s": schedule["id"], "q": quarter},
        )


async def resource_of(ctx: AuthContext, schedule: Mapping[str, Any]) -> Resource:  # Any: a row
    """A basis return's engagement, or the firm for a schedule without one (the matrix's
    `estimate_schedule.*` rows have no function condition, so the firm check holds; walls were
    applied by `row_of`)."""
    basis = schedule["basis_tax_return_id"]
    if basis is None:
        return Resource.firm(ctx.tenant_id)
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, "tax_return")}
    if basis not in facts:
        raise NotFound("estimate_schedule")
    return await on_return(ctx, facts[basis].engagement_id, basis)


async def patch_schedule(
    ctx: AuthContext,
    schedule_id: UUID,
    *,
    expected_version: int,
    values: Mapping[str, object],
) -> None:
    row = await row_of(ctx, schedule_id)
    await authorise(ctx, UPDATE, await resource_of(ctx, row.schedule))
    if values.get("prior_year_tax") is not None and values.get("prior_year_tax_source") is None:
        raise PriorTaxNeedsSource
    async with uow(ctx.tenant) as tx:
        current = (
            (
                await tx.session.execute(
                    text("SELECT * FROM estimate_schedules WHERE id = :id FOR UPDATE"),
                    {"id": schedule_id},
                )
            )
            .mappings()
            .one()
        )
        if current["row_version"] != expected_version:
            raise EstimateMoved(facts={"current": current["row_version"]})
        merged = dict(current)
        for key in (
            "method",
            "prior_year_tax",
            "prior_agi_over_threshold",
            "projected_withholding",
            "payment_method_label",
        ):
            if key in values:
                merged[key] = values[key]
        source = values.get("prior_year_tax_source")
        await tx.session.execute(
            text(
                "UPDATE estimate_schedules SET method = :method, prior_year_tax = :tax, "
                "prior_year_tax_ref = coalesce(CAST(:ref AS jsonb), prior_year_tax_ref), "
                "prior_agi_over_threshold = :over, projected_withholding = :w, "
                "payment_method_label = :label, row_version = row_version + 1 WHERE id = :id"
            ),
            {
                "method": merged["method"],
                "tax": merged["prior_year_tax"],
                "ref": json.dumps({"source": source}) if source else None,
                "over": merged["prior_agi_over_threshold"],
                "w": merged["projected_withholding"],
                "label": merged["payment_method_label"],
                "id": schedule_id,
            },
        )
        await _recompute(tx, merged)
        tx.record(
            "estimate_schedule.inputs_updated",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(version=int(current["row_version"]) + 1),
        )


async def patch_installment(
    ctx: AuthContext,
    schedule_id: UUID,
    quarter: int,
    *,
    expected_version: int,
    scheduled_for: date | None,
    paid_on: date | None,
    evidence_version_id: UUID | None,
) -> None:
    """`paid_on` needs the evidence it rests on; `scheduled_for` records the client's date."""
    row = await row_of(ctx, schedule_id)
    await authorise(ctx, UPDATE, await resource_of(ctx, row.schedule))
    if paid_on is not None and evidence_version_id is None:
        raise PaidNeedsEvidence
    async with uow(ctx.tenant) as tx:
        current = (
            (
                await tx.session.execute(
                    text(
                        "SELECT * FROM estimate_installments WHERE schedule_id = :s "
                        "AND quarter = :q FOR UPDATE"
                    ),
                    {"s": schedule_id, "q": quarter},
                )
            )
            .mappings()
            .first()
        )
        if current is None:
            raise NotFound("estimate_installment")
        if current["row_version"] != expected_version:
            raise EstimateMoved(facts={"current": current["row_version"]})
        status = (
            "paid" if paid_on is not None else "scheduled" if scheduled_for else current["status"]
        )
        await tx.session.execute(
            text(
                "UPDATE estimate_installments SET status = :status, "
                "scheduled_for = coalesce(:sched, scheduled_for), "
                "paid_on = coalesce(:paid, paid_on), "
                "paid_evidence_version_id = coalesce(:ev, paid_evidence_version_id), "
                "row_version = row_version + 1 WHERE id = :id"
            ),
            {
                "status": status,
                "sched": scheduled_for,
                "paid": paid_on,
                "ev": evidence_version_id,
                "id": current["id"],
            },
        )
        tx.record(
            "estimate_installment.recorded",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(quarter=quarter),
        )


async def _basis(ctx: AuthContext, row: ScheduleRow) -> tuple[UUID, UUID]:
    basis = row.schedule["basis_tax_return_id"]
    if basis is None:
        raise NoBasisReturn
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, "tax_return")}
    if basis not in facts:
        raise NotFound("estimate_schedule")
    return facts[basis].engagement_id, basis


async def request_confirmation(
    ctx: AuthContext, schedule_id: UUID, quarter: int, contact_id: UUID | None
) -> ConfirmationSent:
    row = await row_of(ctx, schedule_id)
    found = row.installment(quarter)
    if found is None:
        raise NotFound("estimate_installment")
    engagement_id, basis = await _basis(ctx, row)
    await authorise(ctx, SEND, await on_return(ctx, engagement_id, basis))

    async def link(tx: UnitOfWork, item_id: UUID) -> None:
        await tx.session.execute(
            text(
                "UPDATE estimate_installments SET status = CASE WHEN status = 'not_confirmed' "
                "THEN 'confirmation_requested' ELSE status END, "
                "confirmation_request_item_id = :item, row_version = row_version + 1 "
                "WHERE id = :id"
            ),
            {"item": item_id, "id": found["id"]},
        )
        tx.record(
            "estimate_installment.confirmation_requested",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(quarter=quarter, item=item_id),
        )

    return await send_confirmation(
        ctx,
        engagement_id,
        description=(
            f"Please confirm your {row.schedule['tax_year']} Q{quarter} "
            f"{row.schedule['jurisdiction']} estimated payment"
        ),
        due_on=found["due_on"],
        contact_id=contact_id,
        wave="year_end",
        linked_ref={"type": "estimate_schedule", "id": str(schedule_id), "quarter": quarter},
        link=link,
    )


async def draft_follow_up(
    ctx: AuthContext, schedule_id: UUID, quarter: int
) -> tuple[UUID, UUID, str]:
    """Resend reminder: a draft over the installment's confirmation request, from the approved
    Reminder template. Nothing is sent until a person clicks Send (DEC-74)."""
    from abacus.modules.agents.api import draft_follow_ups

    row = await row_of(ctx, schedule_id)
    found = row.installment(quarter)
    if found is None or found["confirmation_request_item_id"] is None:
        raise NotFound("estimate_installment")
    item_id = found["confirmation_request_item_id"]
    drafted = await draft_follow_ups(ctx, [], [item_id])
    if not drafted:
        raise NotFound("follow_up")
    return drafted[0].id, item_id, "reminder"


async def create_schedule(
    ctx: AuthContext,
    *,
    client_entity_id: UUID,
    basis_tax_return_id: UUID | None,
    tax_year: int,
    jurisdiction: str,
    form: str,
    method: str,
    due_dates: Sequence[tuple[int, date, UUID | None]],
) -> UUID:
    """T-03-T15's content path (service, never constants): a schedule and its four installments,
    dated from C21 by the caller."""
    await authorise(
        ctx, UPDATE, await resource_of(ctx, {"basis_tax_return_id": basis_tax_return_id})
    )
    schedule_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO estimate_schedules (id, tenant_id, client_entity_id, "
                "basis_tax_return_id, tax_year, jurisdiction, form, method, created_by) VALUES "
                "(:id, :t, :c, :b, :y, :j, :f, :m, :by)"
            ),
            {
                "id": schedule_id,
                "t": ctx.tenant_id,
                "c": client_entity_id,
                "b": basis_tax_return_id,
                "y": tax_year,
                "j": jurisdiction,
                "f": form,
                "m": method,
                "by": ctx.user_id,
            },
        )
        for quarter, due_on, rules in due_dates:
            await tx.session.execute(
                text(
                    "INSERT INTO estimate_installments (id, tenant_id, schedule_id, quarter, "
                    "due_on, due_rules_version_id, status) VALUES (:id, :t, :s, :q, :d, :r, :st)"
                ),
                {
                    "id": uuid4(),
                    "t": ctx.tenant_id,
                    "s": schedule_id,
                    "q": quarter,
                    "d": due_on,
                    "r": rules,
                    "st": "not_required" if method in _NOT_REQUIRED else "not_confirmed",
                },
            )
        tx.record(
            "estimate_schedule.created",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(tax_year=tax_year),
        )
    return schedule_id


# --- DF-08: the payments union ------------------------------------------------------------------


@dataclass(frozen=True)
class PaymentRow:
    source_kind: str
    source_id: UUID
    tax_return_id: UUID | None
    client_name: str
    jurisdiction: str
    amount: Decimal
    paid_on: date | None
    confirmation_evidence_version_id: UUID | None


async def payments(ctx: AuthContext, tax_year: int) -> list[PaymentRow]:
    """Approved extension payments and PTET on visible returns, and paid installments of visible
    clients, read only. A proposal isn't a payment; a superseded row isn't one either."""
    facts = await readable_returns(ctx)
    out: list[PaymentRow] = []
    async with tenant_session(ctx.tenant) as session:
        if facts:
            found = await session.execute(
                text(
                    "SELECT p.id, p.kind, p.amount, p.paid_on, "
                    "p.confirmation_evidence_version_id, e.tax_return_id, e.jurisdiction "
                    "FROM extension_payments p JOIN filing_extensions e "
                    "ON e.id = p.filing_extension_id WHERE e.tax_year = :y "
                    "AND e.tax_return_id = ANY(:ids) AND p.approved_by IS NOT NULL "
                    "AND NOT EXISTS (SELECT 1 FROM extension_payments s "
                    "WHERE s.supersedes_id = p.id) ORDER BY p.approved_at, p.id"
                ),
                {"y": tax_year, "ids": list(facts)},
            )
            out += [
                PaymentRow(
                    str(p["kind"]),
                    p["id"],
                    p["tax_return_id"],
                    facts[p["tax_return_id"]].client_name,
                    str(p["jurisdiction"]),
                    Decimal(str(p["amount"])),
                    p["paid_on"],
                    p["confirmation_evidence_version_id"],
                )
                for p in found.mappings()
            ]
    for row in await rows(ctx, tax_year):
        for i in row.installments:
            if i["status"] == "paid" and i["amount"] is not None:
                out.append(
                    PaymentRow(
                        "estimate_installment",
                        i["id"],
                        row.schedule["basis_tax_return_id"],
                        row.client_name,
                        str(row.schedule["jurisdiction"]),
                        Decimal(str(i["amount"])),
                        i["paid_on"],
                        i["paid_evidence_version_id"],
                    )
                )
    return out


# --- TaxCalendarSweep's digest half (T-03-T07) --------------------------------------------------


async def send_due_soon(tenant: TenantContext) -> int:
    """Installments due within the week and not confirmed, one event each, to the people on the
    basis return. The digest writes nothing to a client (no amounts in the notification)."""
    on = await today(tenant)
    async with tenant_session(tenant) as session:
        found = list(
            (
                await session.execute(
                    text(
                        "SELECT i.schedule_id, i.quarter, s.basis_tax_return_id "
                        "FROM estimate_installments i JOIN estimate_schedules s "
                        "ON s.id = i.schedule_id WHERE i.status IN ('not_confirmed', "
                        "'confirmation_requested') AND i.due_on >= :on "
                        "AND i.due_on <= CAST(:on AS date) + CAST(:days AS integer) "
                        "AND s.basis_tax_return_id IS NOT NULL"
                    ),
                    {"on": on, "days": DUE_SOON_DAYS},
                )
            ).mappings()
        )
    sent = 0
    for row in found:
        holders = await function_holders(tenant, row["basis_tax_return_id"])
        people = sorted({user for group in holders.values() for user in group}, key=str)
        if not people:
            continue
        async with uow(tenant) as tx:
            tx.record(
                "estimate_installment.due_soon_notified",
                target=Target("estimate_schedule", row["schedule_id"]),
                after=Ref(quarter=int(row["quarter"]), recipients=len(people)),
            )
            tx.emit(
                EstimateDueSoon(
                    schedule_id=row["schedule_id"],
                    quarter=int(row["quarter"]),
                    recipient_user_ids=people,
                )
            )
        sent += 1
    return sent


async def send_due_soon_all() -> int:
    total = 0
    for tenant_id in await firm_tenant_ids():
        total += await send_due_soon(TenantContext(tenant_id, "system", "tax:estimates"))
    return total
