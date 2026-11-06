"""T-03-T07: estimate schedules (TAX-13 b; T-03 §3 F5; DEC-2327).

A schedule is one client's estimated tax for a tax year and jurisdiction. A person enters the
inputs (the method, the prior-year tax, withholding); code computes the annual payment and its
quarters (`tax.compute.payments`, stamped), and the dates come from published rules. Nothing here
takes a bank account or initiates a payment (DEC-89): a method is a label.

A schedule hangs off a client, so the wall is the client's (`walled_from`), and an installment's
confirmation request goes in the basis return's engagement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import today
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.identity.api import AuthContext, walled_from
from abacus.modules.tax.compute.payments import (
    Stamp,
    installment_amounts,
    parameters,
    required_annual_payment,
)
from abacus.modules.tax.due_dates import installments_due

KIND: Final = "tax_return"
_RETURN_KIND: Final = "tax_return"
OWED: Final = frozenset({"prior_year_100", "prior_year_110", "current_year_90"})


class ScheduleMoved(DomainConflict):
    code = "version_conflict"


class NoBasisReturn(DomainConflict):
    """A confirmation request needs the basis return's engagement to live in."""

    code = "no_basis_return"


class InstallmentNotRequired(DomainInvalid):
    code = "installment_not_required"


@dataclass(frozen=True)
class Installment:
    quarter: int
    due_on: date
    amount: Decimal | None
    status: str
    scheduled_for: date | None
    paid_on: date | None
    confirmation_request_item_id: UUID | None
    row_version: int


@dataclass(frozen=True)
class Schedule:
    id: UUID
    client_entity_id: UUID
    client_id: UUID
    client_name: str
    basis_tax_return_id: UUID | None
    tax_year: int
    jurisdiction: str
    form: str
    method: str
    prior_year_tax: Decimal | None
    prior_agi_over_threshold: bool | None
    projected_withholding: Decimal | None
    annual_required: Decimal | None
    payment_method_label: str | None
    engine_version: str | None
    inputs_hash: str | None
    row_version: int
    installments: tuple[Installment, ...]


def _computed(row: dict[str, Any]) -> tuple[Decimal | None, Stamp | None, tuple[Decimal, ...]]:
    """The annual payment and quarters, or nothing for a not-required or prospect method, or a
    year whose parameters aren't published (never a guess)."""
    if row["method"] not in OWED:
        return None, None, ()
    try:
        params = parameters(int(row["tax_year"]))
    except LookupError:
        return None, None, ()
    annual = required_annual_payment(
        row["method"],
        prior_year_tax=row["prior_year_tax"],
        projected_withholding=row["projected_withholding"],
        current_year_tax=row["prior_year_tax"] if row["method"] == "current_year_90" else None,
        params=params,
    )
    if annual.annual is None:
        return None, annual.stamp, ()
    return annual.annual, annual.stamp, installment_amounts(annual.annual, params).amounts


async def _write_quarters(tx: UnitOfWork, ctx: AuthContext, row: dict[str, Any]) -> None:
    """Quarters from rules and code. A paid or scheduled quarter keeps its status; a schedule that
    owes nothing has every open quarter `not_required`."""
    annual, _, amounts = _computed(row)
    dates = await installments_due(row["form"], int(row["tax_year"]), row["jurisdiction"])
    for quarter, due_on in sorted(dates.items()):
        amount = amounts[quarter - 1] if quarter <= len(amounts) else None
        status = "not_required" if annual is None else "not_confirmed"
        await tx.session.execute(
            text(
                "INSERT INTO estimate_installments (tenant_id, schedule_id, quarter, due_on, "
                "amount, status) VALUES (:t, :s, :q, :d, :a, :st) "
                "ON CONFLICT (tenant_id, schedule_id, quarter) DO UPDATE SET due_on = :d, "
                "amount = :a, status = CASE WHEN estimate_installments.status IN "
                "('not_confirmed', 'not_required') THEN :st ELSE estimate_installments.status "
                "END, row_version = estimate_installments.row_version + 1"
            ),
            {
                "t": ctx.tenant_id,
                "s": row["id"],
                "q": quarter,
                "d": due_on,
                "a": amount,
                "st": status,
            },
        )


async def create(
    ctx: AuthContext,
    client_entity_id: UUID,
    *,
    basis_tax_return_id: UUID | None,
    tax_year: int,
    jurisdiction: str,
    form: str,
    method: str,
    prior_year_tax: Decimal | None,
    prior_agi_over_threshold: bool | None,
    projected_withholding: Decimal | None,
    payment_method_label: str | None,
) -> UUID:
    """A schedule and its quarters, through this one door (T-03-T15 loads through it too)."""
    walled = await walled_from(ctx.tenant, ctx.user_id)
    async with uow(ctx.tenant) as tx:
        client = (
            await tx.session.execute(
                text("SELECT client_id FROM client_entities WHERE id = :e"),
                {"e": client_entity_id},
            )
        ).scalar_one_or_none()
        if client is None or client in walled:
            raise NotFound("client_entity")
        row: dict[str, Any] = {  # Any: JSON from the database
            "tax_year": tax_year,
            "jurisdiction": jurisdiction,
            "form": form,
            "method": method,
            "prior_year_tax": prior_year_tax,
            "projected_withholding": projected_withholding,
        }
        annual, stamp, _ = _computed(row)
        row["id"] = (
            await tx.session.execute(
                text(
                    "INSERT INTO estimate_schedules (tenant_id, client_entity_id, "
                    "basis_tax_return_id, tax_year, jurisdiction, form, method, prior_year_tax, "
                    "prior_agi_over_threshold, projected_withholding, annual_required, "
                    "engine_version, inputs_hash, payment_method_label, created_by) VALUES (:t, "
                    ":e, :b, :y, :j, :f, :m, :p, :a, :w, :r, :v, :h, :l, :by) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": client_entity_id,
                    "b": basis_tax_return_id,
                    "y": tax_year,
                    "j": jurisdiction,
                    "f": form,
                    "m": method,
                    "p": prior_year_tax,
                    "a": prior_agi_over_threshold,
                    "w": projected_withholding,
                    "r": annual,
                    "v": stamp.engine_version if stamp and annual is not None else None,
                    "h": stamp.inputs_hash if stamp and annual is not None else None,
                    "l": payment_method_label,
                    "by": ctx.user_id,
                },
            )
        ).scalar_one()
        await _write_quarters(tx, ctx, row)
        tx.record(
            "estimate_schedule.created",
            target=Target("estimate_schedule", row["id"]),
            after=Ref(tax_year=tax_year),
        )
    return row["id"]


async def schedules(ctx: AuthContext, tax_year: int) -> list[Schedule]:
    """The year's schedules, less the clients the viewer is walled off from."""
    walled = await walled_from(ctx.tenant, ctx.user_id)
    async with tenant_session(ctx.tenant) as session:
        heads = (
            (
                await session.execute(
                    text(
                        "SELECT s.*, e.client_id, e.name AS client_name FROM estimate_schedules s "
                        "JOIN client_entities e ON e.id = s.client_entity_id "
                        "WHERE s.tax_year = :y ORDER BY e.name, s.jurisdiction"
                    ),
                    {"y": tax_year},
                )
            )
            .mappings()
            .all()
        )
        shown = [h for h in heads if h["client_id"] not in walled]
        quarters = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM estimate_installments WHERE schedule_id = ANY(:ids) "
                        "ORDER BY schedule_id, quarter"
                    ),
                    {"ids": [h["id"] for h in shown]},
                )
            )
            .mappings()
            .all()
        )
    return [_schedule(h, [q for q in quarters if q["schedule_id"] == h["id"]]) for h in shown]


def _schedule(h: Mapping[str, Any], quarters: Sequence[Mapping[str, Any]]) -> Schedule:
    # Any: columns of a result mapping
    return Schedule(
        h["id"],
        h["client_entity_id"],
        h["client_id"],
        h["client_name"],
        h["basis_tax_return_id"],
        h["tax_year"],
        h["jurisdiction"],
        h["form"],
        h["method"],
        h["prior_year_tax"],
        h["prior_agi_over_threshold"],
        h["projected_withholding"],
        h["annual_required"],
        h["payment_method_label"],
        h["engine_version"],
        h["inputs_hash"],
        h["row_version"],
        tuple(
            Installment(
                q["quarter"],
                q["due_on"],
                q["amount"],
                q["status"],
                q["scheduled_for"],
                q["paid_on"],
                q["confirmation_request_item_id"],
                q["row_version"],
            )
            for q in quarters
        ),
    )


async def one(ctx: AuthContext, schedule_id: UUID) -> Schedule:
    walled = await walled_from(ctx.tenant, ctx.user_id)
    async with tenant_session(ctx.tenant) as session:
        head = (
            (
                await session.execute(
                    text(
                        "SELECT s.*, e.client_id, e.name AS client_name FROM estimate_schedules s "
                        "JOIN client_entities e ON e.id = s.client_entity_id WHERE s.id = :s"
                    ),
                    {"s": schedule_id},
                )
            )
            .mappings()
            .first()
        )
        if head is None or head["client_id"] in walled:
            raise NotFound("estimate_schedule")
        quarters = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM estimate_installments WHERE schedule_id = :s "
                        "ORDER BY quarter"
                    ),
                    {"s": schedule_id},
                )
            )
            .mappings()
            .all()
        )
    return _schedule(head, quarters)


async def patch(
    ctx: AuthContext,
    schedule_id: UUID,
    *,
    expected_version: int,
    changes: dict[str, Any],  # Any: the patch's own fields
) -> Schedule:
    """Inputs, then code recomputes the annual payment and the open quarters."""
    current = await one(ctx, schedule_id)
    if current.row_version != expected_version:
        raise ScheduleMoved(facts={"current": current.row_version})
    row: dict[str, Any] = {  # Any: JSON from the database
        "id": schedule_id,
        "tax_year": current.tax_year,
        "jurisdiction": current.jurisdiction,
        "form": current.form,
        "method": changes.get("method") or current.method,
        "prior_year_tax": changes.get("prior_year_tax", current.prior_year_tax),
        "prior_agi_over_threshold": changes.get(
            "prior_agi_over_threshold", current.prior_agi_over_threshold
        ),
        "projected_withholding": changes.get(
            "projected_withholding", current.projected_withholding
        ),
        "payment_method_label": changes.get("payment_method_label", current.payment_method_label),
    }
    annual, stamp, _ = _computed(row)
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.execute(
            text(
                "UPDATE estimate_schedules SET method = :m, prior_year_tax = :p, "
                "prior_agi_over_threshold = :a, projected_withholding = :w, annual_required = :r, "
                "engine_version = :v, inputs_hash = :h, payment_method_label = :l, "
                "row_version = row_version + 1 WHERE id = :id AND row_version = :seen RETURNING id"
            ),
            {
                "m": row["method"],
                "p": row["prior_year_tax"],
                "a": row["prior_agi_over_threshold"],
                "w": row["projected_withholding"],
                "r": annual,
                "v": stamp.engine_version if stamp and annual is not None else None,
                "h": stamp.inputs_hash if stamp and annual is not None else None,
                "l": row["payment_method_label"],
                "id": schedule_id,
                "seen": expected_version,
            },
        )
        if moved.first() is None:
            raise ScheduleMoved
        await _write_quarters(tx, ctx, row)
        tx.record(
            "estimate_schedule.updated",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(row_version=expected_version + 1),
        )
    return await one(ctx, schedule_id)


async def patch_installment(
    ctx: AuthContext,
    schedule_id: UUID,
    quarter: int,
    *,
    expected_version: int,
    scheduled_for: date | None,
    paid_on: date | None,
) -> Schedule:
    current = await one(ctx, schedule_id)
    found = next((q for q in current.installments if q.quarter == quarter), None)
    if found is None:
        raise NotFound("estimate_installment")
    if found.row_version != expected_version:
        raise ScheduleMoved(facts={"current": found.row_version})
    if found.status == "not_required":
        raise InstallmentNotRequired
    status = "paid" if paid_on else "scheduled" if scheduled_for else found.status
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE estimate_installments SET scheduled_for = :sf, paid_on = :po, "
                "status = :st, row_version = row_version + 1 "
                "WHERE schedule_id = :s AND quarter = :q"
            ),
            {
                "sf": scheduled_for or found.scheduled_for,
                "po": paid_on or found.paid_on,
                "st": status,
                "s": schedule_id,
                "q": quarter,
            },
        )
        tx.record(
            "estimate_installment.updated",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(quarter=quarter),
        )
    return await one(ctx, schedule_id)


async def request_confirmation(
    ctx: AuthContext, schedule_id: UUID, quarter: int
) -> tuple[Any, Schedule]:  # Any: the request item's view
    """One confirmation request in the basis return's engagement (a prospect has none)."""
    from abacus.modules.requests.api import NewRequestItem, add_request_item

    current = await one(ctx, schedule_id)
    found = next((q for q in current.installments if q.quarter == quarter), None)
    if found is None:
        raise NotFound("estimate_installment")
    if current.basis_tax_return_id is None:
        raise NoBasisReturn
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, _RETURN_KIND)}
    fact = facts.get(current.basis_tax_return_id)
    if fact is None:
        raise NotFound("estimate_schedule")
    item = await add_request_item(
        ctx,
        fact.engagement_id,
        NewRequestItem(
            description=f"Please confirm your Q{quarter} {current.form} estimated payment",
            audit_area="tax_payments",
        ),
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE estimate_installments SET status = CASE WHEN status = 'not_confirmed' "
                "THEN 'confirmation_requested' ELSE status END, "
                "confirmation_request_item_id = :item, row_version = row_version + 1 "
                "WHERE schedule_id = :s AND quarter = :q"
            ),
            {"item": item.id, "s": schedule_id, "q": quarter},
        )
        tx.record(
            "estimate_installment.confirmation_requested",
            target=Target("estimate_schedule", schedule_id),
            after=Ref(quarter=quarter),
        )
    return item, await one(ctx, schedule_id)


def quarter_of(rows: list[Schedule], quarter: int | None) -> int:
    """The named quarter, else the next one due, else the last."""
    if quarter is not None:
        return quarter
    on = today()
    due = sorted(q.due_on for s in rows for q in s.installments if q.due_on >= on)
    if not due:
        return 4
    for s in rows:
        for q in s.installments:
            if q.due_on == due[0]:
                return q.quarter
    return 4


def tile_counts(rows: list[Schedule], quarter: int) -> dict[str, int]:
    """TAX-13 b: Q due = Paid + Scheduled + Awaiting confirmation; Not required apart."""
    statuses = [q.status for s in rows for q in s.installments if q.quarter == quarter]
    counts = {
        "paid": statuses.count("paid"),
        "scheduled": statuses.count("scheduled"),
        "confirmation_requested": statuses.count("confirmation_requested")
        + statuses.count("not_confirmed"),
        "not_required": statuses.count("not_required"),
    }
    counts["due"] = counts["paid"] + counts["scheduled"] + counts["confirmation_requested"]
    return counts


__all__ = [
    "Installment",
    "NoBasisReturn",
    "Schedule",
    "ScheduleMoved",
    "create",
    "one",
    "patch",
    "patch_installment",
    "quarter_of",
    "request_confirmation",
    "schedules",
    "tile_counts",
]
