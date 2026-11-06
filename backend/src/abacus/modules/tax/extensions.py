"""T-03-T07: extensions (TAX-13 a; T-03 §3 F5; DEC-2243).

- **Rows.** Filing extensions grouped per return, only for returns the viewer may see
  (`engagements.api.work_item_facts`, walls applied), with the counts from those rows alone:
  `{extended, open, filed, likely, acks_pending}` (DEC-43: a walled return is absent, never
  counted).
- **Approve and request.** One unit of work as the caller (a person; the matrix holds the
  reviewer function): every proposed payment on the chosen extensions is approved, then one
  confirmation request item is created per return in its binder's engagement, attributed to the
  caller. A payment is a method label and an amount; no route stores or transmits an instrument.
- **Prepare and submit.** Prepare writes a return's lines with the preparer's projected liability
  and code's safe-harbor target, and proposes payments (a later change supersedes). The G1 and G3
  gates hold it (409 `gate_unmet`). Submit opens C13's gate for the return's reviewers.
- **Mark filed** is a person's record (date, form, the filed form's evidence version); Accrued
  never transmits an extension (DEC-49).

Figures (projected liability, the safe-harbor target) are stored by code with their engine stamp
(T-03-T04's `tax.compute.payments`); this module reads them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.engagements.api import WorkItemFacts, gate_fact, work_item_facts
from abacus.modules.identity.api import AuthContext, Resource, authorise, engagement_resource
from abacus.modules.tax.compute.payments import paid_by_original_due, parameters, safe_harbor
from abacus.modules.tax.due_dates import dates_for

KIND = "tax_return"
PREPARE: Final = "filing_extension.prepare"
APPROVE: Final = "filing_extension.approve_payment"
SEND: Final = "filing_extension.confirmation_send"
FEDERAL: Final = "US"
# The federal extension form for a return's form (the Code's, not the firm's: DEC-76). A state
# line names its own form.
EXTENSION_FORM: Final = {
    "1040": "4868",
    "1040x": "4868",
    "1041": "7004",
    "1065": "7004",
    "1120": "7004",
    "1120s": "7004",
    "990": "8868",
    "706": "4768",
    "709": "8892",
}
_GATES: Final = ("G1", "G3")


class NothingToApprove(DomainConflict):
    """None of the chosen extensions has a proposed payment."""

    code = "nothing_to_approve"


class FiledNeedsEvidence(DomainInvalid):
    """A filed record names the date and the filed form's evidence version."""

    code = "filed_needs_evidence"


class ExtensionMoved(DomainConflict):
    code = "version_conflict"


class GateUnmet(DomainConflict):
    """The engagement isn't accepted or has no letter, so the extension can't be prepared."""

    code = "gate_unmet"


class StateLineNeedsForm(DomainInvalid):
    """Only a federal line's extension form follows from the return."""

    code = "extension_form_required"


class ExtensionSubmitted(DomainEvent):
    """T-03-T07: C13's gate opens; a payment's approval closes it. Identifiers only."""

    event_type: ClassVar[str] = "filing_extension.submitted"

    extension_id: Annotated[UUID, classified("internal")]


class ExtensionPaymentApproved(DomainEvent):
    event_type: ClassVar[str] = "extension_payment.approved"

    extension_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class LineIn:
    """A preparer's line. Accrued never computes the projected tax (T-03 US-4.2)."""

    return_id: UUID
    jurisdiction: str = FEDERAL
    form: str | None = None
    projected_liability: Decimal | None = None
    projected_liability_source: str | None = None
    withholding_plus_estimates: Decimal | None = None


@dataclass(frozen=True)
class PaymentIn:
    return_id: UUID
    jurisdiction: str
    kind: str
    amount: Decimal


@dataclass(frozen=True)
class Check:
    """The sheet's check line, from code."""

    tax_return_id: UUID
    jurisdiction: str
    projected_liability: Decimal | None
    safe_harbor_target: Decimal | None
    paid_by_original_due: Decimal | None
    meets_safe_harbor: bool | None
    engine_name: str | None
    engine_version: str | None
    inputs_hash: str | None


@dataclass
class ReturnRow:
    tax_return_id: UUID
    work_item_id: UUID
    engagement_id: UUID
    client_name: str
    tax_year: int
    lines: list[dict[str, Any]] = field(  # Any: JSON from the database
        default_factory=list[dict[str, Any]]  # Any: JSON from the database
    )  # Any: JSON from the database or the document
    payments: list[dict[str, Any]] = field(  # Any: JSON from the database
        default_factory=list[dict[str, Any]]  # Any: JSON from the database
    )  # Any: JSON from the database or the document

    @property
    def likely(self) -> bool:
        return any(line["likely_to_extend"] for line in self.lines)


def segment_of(row: ReturnRow) -> str:
    """TAX-13 a's three views: Open, Filed & acks, Likely to extend."""
    if row.likely and all(x["status"] == "not_filed" for x in row.lines):
        return "likely"
    return (
        "filed"
        if all(x["status"] in ("filed", "accepted", "rejected") for x in row.lines)
        else "open"
    )


def counts(rows: Sequence[ReturnRow]) -> dict[str, int]:
    lines = [line for r in rows for line in r.lines]
    return {
        "extended": sum(1 for r in rows if any(x["status"] != "not_filed" for x in r.lines)),
        "open": sum(1 for x in lines if x["status"] in ("not_filed", "prepared")),
        "filed": sum(1 for x in lines if x["status"] in ("filed", "accepted")),
        "likely": sum(1 for r in rows if r.likely),
        "acks_pending": sum(1 for x in lines if x["status"] == "filed"),
    }


async def rows(ctx: AuthContext, tax_year: int) -> list[ReturnRow]:
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    if not facts:
        return []
    async with tenant_session(ctx.tenant) as session:
        lines = (
            await session.execute(
                text(
                    "SELECT * FROM filing_extensions WHERE tax_year = :y "
                    "AND tax_return_id = ANY(:ids) ORDER BY tax_return_id, jurisdiction"
                ),
                {"y": tax_year, "ids": list(facts)},
            )
        ).mappings()
        out: dict[UUID, ReturnRow] = {}
        ext_ids: list[UUID] = []
        for line in lines:
            f = facts[line["tax_return_id"]]
            row = out.setdefault(
                line["tax_return_id"],
                ReturnRow(
                    line["tax_return_id"], f.work_item_id, f.engagement_id, f.client_name, tax_year
                ),
            )
            row.lines.append(dict(line))
            ext_ids.append(line["id"])
        if ext_ids:
            payments = (
                await session.execute(
                    text(
                        "SELECT p.*, e.tax_return_id, e.jurisdiction FROM extension_payments p "
                        "JOIN filing_extensions e ON e.id = p.filing_extension_id "
                        "WHERE p.filing_extension_id = ANY(:ids) AND NOT EXISTS (SELECT 1 FROM "
                        "extension_payments s WHERE s.supersedes_id = p.id) ORDER BY p.proposed_at"
                    ),
                    {"ids": ext_ids},
                )
            ).mappings()
            for p in payments:
                out[p["tax_return_id"]].payments.append(dict(p))
    return sorted(out.values(), key=lambda r: r.client_name.lower())


async def approve_and_request(
    ctx: AuthContext, extension_ids: Sequence[UUID], *, send_confirmations: bool
) -> tuple[list[UUID], list[UUID]]:
    """Approve every proposed payment on the extensions as the caller, then one confirmation
    request per return (attributed to the caller)."""
    from abacus.modules.requests.api import NewRequestItem, add_request_item

    if send_confirmations:
        # A person sends the confirmation requests; the agent never does (AGENT-001).
        await authorise(ctx, "filing_extension.confirmation_send", Resource.firm(ctx.tenant_id))

    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    async with tenant_session(ctx.tenant) as session:
        returns = (
            await session.execute(
                text("SELECT DISTINCT tax_return_id FROM filing_extensions WHERE id = ANY(:ids)"),
                {"ids": list(extension_ids)},
            )
        ).scalars()
        chosen = [r for r in returns if r in visible]
    # The reviewer function is the return's, so the firm-level gate can't decide it (US-4.4).
    for return_id in chosen:
        await _narrow(ctx, APPROVE, visible[return_id])
    async with uow(ctx.tenant) as tx:
        pending = list(
            (
                await tx.session.execute(
                    text(
                        "SELECT p.id, p.amount, e.id AS extension_id, e.tax_return_id, "
                        "e.jurisdiction, e.form "
                        "FROM extension_payments p JOIN filing_extensions e "
                        "ON e.id = p.filing_extension_id WHERE e.id = ANY(:ids) "
                        "AND p.approved_by IS NULL FOR UPDATE OF p"
                    ),
                    {"ids": list(extension_ids)},
                )
            ).mappings()
        )
        pending = [p for p in pending if p["tax_return_id"] in visible]
        if not pending:
            raise NothingToApprove
        await tx.session.execute(
            text(
                "UPDATE extension_payments SET approved_by = :by, approved_actor_kind = 'human', "
                "approved_at = abacus_now() WHERE id = ANY(:ids)"
            ),
            {"by": ctx.user_id, "ids": [p["id"] for p in pending]},
        )
        touched = list(dict.fromkeys(p["extension_id"] for p in pending))
        await tx.session.execute(
            text(
                "UPDATE filing_extensions SET status = 'prepared', row_version = row_version + 1 "
                "WHERE id = ANY(:ids) AND status = 'not_filed'"
            ),
            {"ids": touched},
        )
        for extension_id in touched:
            tx.emit(ExtensionPaymentApproved(extension_id=extension_id))
        tx.record(
            "extension_payment.approved",
            target=Target("work_item", pending[0]["tax_return_id"]),
            after=Ref(payments=len(pending)),
        )
    approved = [p["id"] for p in pending]
    requested: list[UUID] = []
    if send_confirmations:
        for return_id in dict.fromkeys(p["tax_return_id"] for p in pending):
            mine = [p for p in pending if p["tax_return_id"] == return_id]
            listed = ", ".join(f"{p['form']} {p['jurisdiction']} {p['amount']:,}" for p in mine)
            item = await add_request_item(
                ctx,
                visible[return_id].engagement_id,
                NewRequestItem(
                    description=f"Please confirm your extension payments: {listed}"[:2000],
                    audit_area="tax_payments",
                ),
            )
            requested.append(item.id)
            await _link_confirmation(ctx, return_id, [p["extension_id"] for p in mine], item.id)
    return approved, requested


async def _narrow(ctx: AuthContext, action: str, fact: WorkItemFacts) -> None:
    base = await engagement_resource(ctx.tenant, fact.engagement_id)
    await authorise(ctx, action, replace(base, work_item_id=fact.work_item_id))


async def _link_confirmation(
    ctx: AuthContext, return_id: UUID, extension_ids: Sequence[UUID], item_id: UUID
) -> None:
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE filing_extensions SET confirmation_request_item_id = :item, "
                "row_version = row_version + 1 WHERE id = ANY(:ids)"
            ),
            {"item": item_id, "ids": list(extension_ids)},
        )
        tx.record(
            "filing_extension.confirmation_requested",
            target=Target("work_item", return_id),
            after=Ref(extensions=len(extension_ids), request_item=item_id),
        )


def _check(
    form: str,
    return_id: UUID,
    jurisdiction: str,
    tax_year: int,
    projected: Decimal | None,
    withholding: Decimal | None,
    payments: Sequence[Decimal],
) -> tuple[Check, Decimal | None, Decimal | None]:
    """The check line, the target and its percentage. A year or form without parameters has no
    target, never a guess."""
    try:
        params = parameters(tax_year)
        harbor = safe_harbor(form, projected, params)
    except LookupError:
        return (
            Check(return_id, jurisdiction, projected, None, None, None, None, None, None),
            None,
            None,
        )
    paid = paid_by_original_due(withholding or Decimal(0), list(payments), harbor.target, params)
    return (
        Check(
            return_id,
            jurisdiction,
            projected,
            harbor.target,
            paid.paid_by_original_due,
            paid.meets,
            harbor.stamp.engine_name,
            harbor.stamp.engine_version,
            harbor.stamp.inputs_hash,
        ),
        harbor.target,
        harbor.pct,
    )


async def prepare(
    ctx: AuthContext,
    return_ids: Sequence[UUID],
    *,
    lines: Sequence[LineIn] = (),
    payments: Sequence[PaymentIn] = (),
) -> list[Check]:
    """Each return's lines `prepared`, with its proposed payments. All or nothing."""
    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    chosen = {*return_ids, *(x.return_id for x in lines), *(p.return_id for p in payments)}
    if any(r not in visible for r in chosen):
        raise NotFound(KIND)
    for return_id in chosen:
        fact = visible[return_id]
        await _narrow(ctx, PREPARE, fact)
        met = {g: (await gate_fact(ctx.tenant, fact.engagement_id, g)).met for g in _GATES}
        if not all(met.values()):
            raise GateUnmet(
                facts={"g1_met": met["G1"], "g3_met": met["G3"], "return_id": str(return_id)}
            )
    wanted: dict[tuple[UUID, str], LineIn] = {(r, FEDERAL): LineIn(r) for r in chosen}
    wanted.update({(x.return_id, x.jurisdiction): x for x in lines})
    for p in payments:
        wanted.setdefault((p.return_id, p.jurisdiction), LineIn(p.return_id, p.jurisdiction))
    checks: list[Check] = []
    async with uow(ctx.tenant) as tx:
        heads = {
            r.work_item_id: r
            for r in (
                await tx.session.execute(
                    text(
                        "SELECT work_item_id, form, tax_year, fiscal_year_end FROM tax_returns "
                        "WHERE work_item_id = ANY(:ids)"
                    ),
                    {"ids": list(chosen)},
                )
            ).all()
        }
        for (return_id, jurisdiction), line in wanted.items():
            head = heads[return_id]
            form = line.form or (
                EXTENSION_FORM.get(head.form) if jurisdiction == FEDERAL else None
            )
            if form is None:
                raise StateLineNeedsForm(facts={"jurisdiction": jurisdiction})
            dates = await dates_for(head.form, head.tax_year, head.fiscal_year_end)
            if dates is None or dates.extended_due_on is None:
                raise NotFound("due_date_rule")
            mine = [
                p.amount
                for p in payments
                if p.return_id == return_id and p.jurisdiction == jurisdiction
            ]
            check, target, pct = _check(
                head.form,
                return_id,
                jurisdiction,
                head.tax_year,
                line.projected_liability,
                line.withholding_plus_estimates,
                mine,
            )
            checks.append(check)
            fact = visible[return_id]
            extension_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO filing_extensions (tenant_id, engagement_id, work_item_id, "
                        "tax_return_id, tax_year, jurisdiction, form, status, original_due_on, "
                        "extended_due_on, due_rules_version_id, projected_liability, "
                        "projected_liability_source, withholding_plus_estimates, safe_harbor_pct, "
                        "safe_harbor_target, engine_version, inputs_hash, created_by) VALUES (:t, "
                        ":e, :w, :w, :y, :j, :form, 'prepared', :orig, :ext, :rules, :proj, :src, "
                        ":held, :pct, :target, :engine, :hash, :by) "
                        "ON CONFLICT (tenant_id, tax_return_id, jurisdiction) DO UPDATE SET "
                        "status = CASE WHEN filing_extensions.status = 'not_filed' "
                        "THEN 'prepared' ELSE filing_extensions.status END, "
                        "form = EXCLUDED.form, "
                        "projected_liability = coalesce(EXCLUDED.projected_liability, "
                        "filing_extensions.projected_liability), projected_liability_source = "
                        "coalesce(EXCLUDED.projected_liability_source, "
                        "filing_extensions.projected_liability_source), "
                        "withholding_plus_estimates = "
                        "coalesce(EXCLUDED.withholding_plus_estimates, "
                        "filing_extensions.withholding_plus_estimates), safe_harbor_pct = "
                        "coalesce(EXCLUDED.safe_harbor_pct, filing_extensions.safe_harbor_pct), "
                        "safe_harbor_target = coalesce(EXCLUDED.safe_harbor_target, "
                        "filing_extensions.safe_harbor_target), engine_version = "
                        "coalesce(EXCLUDED.engine_version, filing_extensions.engine_version), "
                        "inputs_hash = coalesce(EXCLUDED.inputs_hash, "
                        "filing_extensions.inputs_hash), "
                        "row_version = filing_extensions.row_version + 1 RETURNING id"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "e": fact.engagement_id,
                        "w": return_id,
                        "y": head.tax_year,
                        "j": jurisdiction,
                        "form": form,
                        "orig": dates.original_due_on,
                        "ext": dates.extended_due_on,
                        "rules": next(iter(dates.reference_set_version_ids), None),
                        "proj": line.projected_liability,
                        "src": line.projected_liability_source,
                        "held": line.withholding_plus_estimates,
                        "pct": pct,
                        "target": target,
                        "engine": check.engine_version if target is not None else None,
                        "hash": check.inputs_hash if target is not None else None,
                        "by": ctx.user_id,
                    },
                )
            ).scalar_one()
            for p in payments:
                if p.return_id != return_id or p.jurisdiction != jurisdiction:
                    continue
                # A later change supersedes; an approved payment never changes.
                earlier = (
                    await tx.session.execute(
                        text(
                            "SELECT p.id FROM extension_payments p WHERE p.filing_extension_id = "
                            ":e AND p.kind = :k AND NOT EXISTS (SELECT 1 FROM extension_payments "
                            "s WHERE s.supersedes_id = p.id) ORDER BY p.proposed_at DESC LIMIT 1"
                        ),
                        {"e": extension_id, "k": p.kind},
                    )
                ).scalar_one_or_none()
                await tx.session.execute(
                    text(
                        "INSERT INTO extension_payments (tenant_id, filing_extension_id, kind, "
                        "amount, proposed_by, supersedes_id) VALUES (:t, :e, :k, :a, :by, :old)"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "e": extension_id,
                        "k": p.kind,
                        "a": p.amount,
                        "by": ctx.user_id,
                        "old": earlier,
                    },
                )
            tx.record(
                "filing_extension.prepared",
                target=Target("work_item", return_id),
                after=Ref(extension=extension_id, payments=len(mine)),
            )
    return checks


async def submit(ctx: AuthContext, extension_ids: Sequence[UUID]) -> int:
    """The preparer's path: C13's gate opens for the return's reviewers. The tax year."""
    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    async with uow(ctx.tenant) as tx:
        found = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, tax_return_id, tax_year FROM filing_extensions "
                        "WHERE id = ANY(:ids) FOR UPDATE"
                    ),
                    {"ids": list(extension_ids)},
                )
            )
            .mappings()
            .all()
        )
        if len(found) != len(set(extension_ids)) or any(
            r["tax_return_id"] not in visible for r in found
        ):
            raise NotFound("filing_extension")
        for row in found:
            await _narrow(ctx, PREPARE, visible[row["tax_return_id"]])
        await tx.session.execute(
            text(
                "UPDATE filing_extensions SET submitted_by = :by, submitted_at = abacus_now(), "
                "row_version = row_version + 1 WHERE id = ANY(:ids)"
            ),
            {"by": ctx.user_id, "ids": [r["id"] for r in found]},
        )
        for row in found:
            tx.emit(ExtensionSubmitted(extension_id=row["id"]))
            tx.record(
                "filing_extension.submitted",
                target=Target("work_item", row["tax_return_id"]),
                after=Ref(extension=row["id"]),
            )
    return int(found[0]["tax_year"])


async def request_confirmation(ctx: AuthContext, extension_id: UUID) -> tuple[Any, UUID]:
    """One confirmation request in the return's binder, sent on the click. Any: the item's view."""
    from abacus.modules.requests.api import NewRequestItem, add_request_item

    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT tax_return_id, jurisdiction, form "
                        "FROM filing_extensions WHERE id = :id"
                    ),
                    {"id": extension_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None or row["tax_return_id"] not in visible:
        raise NotFound("filing_extension")
    fact = visible[row["tax_return_id"]]
    await _narrow(ctx, SEND, fact)
    item = await add_request_item(
        ctx,
        fact.engagement_id,
        NewRequestItem(
            description=f"Please confirm your {row['form']} {row['jurisdiction']} payment",
            audit_area="tax_payments",
        ),
    )
    await _link_confirmation(ctx, row["tax_return_id"], [extension_id], item.id)
    return item, row["tax_return_id"]


async def open_payment_approvals(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[tuple[UUID, UUID, UUID]]:
    """C13: submitted extensions with an unapproved payment (id, engagement, work item)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT e.id, e.engagement_id, e.work_item_id FROM filing_extensions e "
                    "WHERE e.submitted_at IS NOT NULL "
                    "AND (:eng IS NULL OR e.engagement_id = :eng) AND EXISTS (SELECT 1 FROM "
                    "extension_payments p WHERE p.filing_extension_id = e.id "
                    "AND p.approved_by IS NULL AND NOT EXISTS (SELECT 1 FROM extension_payments "
                    "s WHERE s.supersedes_id = p.id))"
                ),
                {"eng": engagement_id},
            )
        ).all()
    return [(r.id, r.engagement_id, r.work_item_id) for r in rows]


async def patch(
    ctx: AuthContext,
    extension_id: UUID,
    *,
    action: str,
    expected_version: int,
    filed_on: date | None,
    form: str | None,
    filed_form_evidence_version_id: UUID | None,
    likely_to_extend: bool | None,
    reason: str | None,
    note: str | None,
) -> int:
    """Mark filed (a person's record with evidence) or flag likely to extend, one or the other;
    against the row version the caller saw. Returns the extension's tax year."""
    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    text("SELECT * FROM filing_extensions WHERE id = :id FOR UPDATE"),
                    {"id": extension_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None or row["tax_return_id"] not in visible:
            raise NotFound("filing_extension")
        await _narrow(ctx, action, visible[row["tax_return_id"]])
        if row["row_version"] != expected_version:
            raise ExtensionMoved(facts={"current": row["row_version"]})
        if filed_on is not None:
            if filed_form_evidence_version_id is None:
                raise FiledNeedsEvidence
            await tx.session.execute(
                text(
                    "UPDATE filing_extensions SET status = 'filed', filed_on = :d, "
                    "form = coalesce(:form, form), filed_recorded_by = :by, "
                    "filed_form_evidence_version_id = :ev, row_version = row_version + 1 "
                    "WHERE id = :id"
                ),
                {
                    "d": filed_on,
                    "form": form,
                    "by": ctx.user_id,
                    "ev": filed_form_evidence_version_id,
                    "id": extension_id,
                },
            )
            tx.record(
                "filing_extension.filed_recorded",
                target=Target("work_item", row["tax_return_id"]),
                after=Ref(extension=extension_id),
            )
            return int(row["tax_year"])
        if likely_to_extend is not None:
            reasons = list(row["likely_reasons"] or [])
            if likely_to_extend and reason and reason not in reasons:
                reasons.append(reason)
            await tx.session.execute(
                text(
                    "UPDATE filing_extensions SET likely_to_extend = :l, likely_reasons = :r, "
                    "likely_note = :n, row_version = row_version + 1 WHERE id = :id"
                ),
                {
                    "l": likely_to_extend,
                    "r": reasons if likely_to_extend else [],
                    "n": note,
                    "id": extension_id,
                },
            )
            tx.record(
                "filing_extension.flagged",
                target=Target("work_item", row["tax_return_id"]),
                after=Ref(likely=int(likely_to_extend)),
            )
    return int(row["tax_year"])


async def years_of(ctx: AuthContext, return_ids: set[UUID]) -> set[int]:
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            text(
                "SELECT DISTINCT tax_year FROM filing_extensions WHERE tax_return_id = ANY(:ids)"
            ),
            {"ids": list(return_ids)},
        )
        return set(found.scalars())


async def year_of(ctx: AuthContext, extension_id: UUID) -> int:
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text("SELECT tax_year FROM filing_extensions WHERE id = :id"),
                {"id": extension_id},
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound("filing_extension")
    return int(found)


async def extensions_of(ctx: AuthContext, return_ids: set[UUID]) -> list[UUID]:
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            text("SELECT id FROM filing_extensions WHERE tax_return_id = ANY(:ids)"),
            {"ids": list(return_ids)},
        )
        return list(found.scalars())


def money(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))
