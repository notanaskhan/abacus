"""T-03-T07: extensions (TAX-13 a, c, d, e; T-03 §3 F4; DEC-2243, DEC-2350).

- **Rows.** Filing extensions grouped per return, only for returns the viewer may see
  (`engagements.api.work_item_facts`, walls applied), with the counts from those rows alone:
  `{extended, open, filed, likely, acks_pending}` (DEC-43: a walled return is absent, never
  counted).
- **Prepare.** G1 and G3 first (409 `gate_unmet` with the facts), then the lines (the federal line
  from the published rules; a state line names its form), the proposed payments (a changed amount
  supersedes the row it changes) and per-line safe-harbor checks by `tax.compute.payments`.
- **Submit for approval.** The proposer's path: the return's reviewers are told, and approve
  through approve-and-request.
- **Approve and request.** One unit of work as the caller (a person; the matrix holds the
  reviewer function on the return): any named returns are prepared, every proposed payment on the
  chosen extensions is approved, and one confirmation request per return is created and sent
  (`requests.send_created`, its Undo window and its grant). A payment is a
  method label and an amount; no route stores or transmits an instrument.
- **Mark filed** is a person's record (date, form, the filed form's evidence version); Accrued
  never transmits an extension (DEC-49).
- **The sweep.** A published reference set recomputes every open line's dates, each change
  audited with both rule versions; a filed line keeps what it was filed under.

Every write authorises on the return (the engagement with the return as the work item), because
`function_in` reads the caller's function there; the firm-level `_gate` only answers client
principals and the flag for these. Figures (projected liability, the safe-harbor target) are
stored by code with their engine stamp (T-03-T04's `tax.compute.payments`); a preparer enters the
projected liability with its source (DEC-77: Accrued never computes tax).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final, cast
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import WorkItemFacts, gate_fact, work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    engagement_resource,
    may_read_unmasked,
    offshore_consented,
)
from abacus.modules.tax.compute import payments as engine
from abacus.modules.tax.due_dates import FORM_FOR_RULES, dates_for
from abacus.modules.tax.engine_adapter import EXTENSION_FORMS

KIND = "tax_return"
FEDERAL: Final = "US"
READ: Final = "filing_extension.read"
PREPARE: Final = "filing_extension.prepare"
APPROVE: Final = "filing_extension.approve_payment"
MARK_FILED: Final = "filing_extension.mark_filed"
SEND: Final = "filing_extension.confirmation_send"
REQUIRED_GATES: Final = ("G1", "G3")
REVIEWER_FUNCTIONS: Final = ("detail_reviewer", "manager_reviewer", "signer")


class ExtensionApprovalRequested(DomainEvent):
    """A preparer submitted extension payments for approval (identifiers only)."""

    event_type: ClassVar[str] = "extension_payment.approval_requested"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


class ExtensionAckRejected(DomainEvent):
    """An imported ack rejected an extension: the preparer and the manager hear (no amounts)."""

    event_type: ClassVar[str] = "extension.ack_rejected"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    extension_id: Annotated[UUID, classified("internal")]
    reject_code: Annotated[str, classified("internal")]  # the agency's code, as filing.py holds it
    recipient_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


class NothingToApprove(DomainConflict):
    """None of the chosen extensions has a proposed payment."""

    code = "nothing_to_approve"


class FiledNeedsEvidence(DomainInvalid):
    """A filed record names the date and the filed form's evidence version."""

    code = "filed_needs_evidence"


class ExtensionMoved(DomainConflict):
    code = "version_conflict"


class ExtensionGateUnmet(DomainConflict):
    """The engagement's G1 or G3 is unmet: an extension can't be prepared (Thornbury's 4768)."""

    code = "gate_unmet"


class NoExtensionForm(DomainConflict):
    """The published rules name no extension form or dates for this return's form."""

    code = "no_extension_form"


class StateFormRequired(DomainInvalid):
    """A state line's first payment names its form (IT-370); only the federal form is a rule's."""

    code = "extension_form_required"


class LiabilityNeedsSource(DomainInvalid):
    """A projected liability carries where it came from (DEC-77, INV-2)."""

    code = "projected_liability_source_required"


@dataclass(frozen=True)
class ProposedPayment:
    return_id: UUID
    jurisdiction: str
    kind: str
    amount: Decimal
    form: str | None = None


@dataclass(frozen=True)
class LineCheck:
    tax_return_id: UUID
    jurisdiction: str
    projected_liability: Decimal | None
    target: Decimal | None
    paid: Decimal
    meets: bool | None
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
    return_form: str = ""

    @property
    def likely(self) -> bool:
        return any(line["likely_to_extend"] for line in self.lines)

    @property
    def primary(self) -> dict[str, Any]:  # Any: JSON from the database
        """The federal line, whose figures the row shows; a state line only without one."""
        return next((x for x in self.lines if x["jurisdiction"] == FEDERAL), self.lines[0])


def counts(rows: Sequence[ReturnRow]) -> dict[str, int]:
    lines = [line for r in rows for line in r.lines]
    return {
        "extended": sum(1 for r in rows if any(x["status"] != "not_filed" for x in r.lines)),
        "open": sum(1 for x in lines if x["status"] in ("not_filed", "prepared")),
        "filed": sum(1 for x in lines if x["status"] in ("filed", "accepted")),
        "likely": sum(1 for r in rows if r.likely),
        "acks_pending": sum(1 for x in lines if x["status"] == "filed"),
    }


def in_segment(row: ReturnRow, segment: str | None) -> bool:
    statuses = {x["status"] for x in row.lines}
    if segment == "likely":
        return row.likely
    if segment == "open":
        return bool(statuses & {"not_filed", "prepared"}) and (
            "not_filed" not in statuses or not row.likely
        )
    if segment == "filed":
        return bool(statuses & {"filed", "accepted", "rejected"})
    return True


def on_tile(row: ReturnRow, tile: str | None) -> bool:
    statuses = {x["status"] for x in row.lines}
    if tile == "extended":
        return statuses != {"not_filed"}
    if tile == "open":
        return bool(statuses & {"not_filed", "prepared"})
    if tile == "filed":
        return bool(statuses & {"filed", "accepted"})
    if tile == "likely":
        return row.likely
    if tile == "acks_pending":
        return "filed" in statuses
    return True


def money(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _parameters(tax_year: int) -> engine.Parameters | None:
    """The year's engine parameters; a year without a file has no target ("—"), never a guess."""
    try:
        return engine.parameters(tax_year)
    except LookupError:
        return None


def line_check(
    return_id: UUID,
    line: Mapping[str, Any],  # Any: a database row
    payments: Sequence[Mapping[str, Any]],  # Any: database rows
    tax_year: int,
) -> LineCheck:
    """Withholding and estimates plus the line's payments made by the original due date, against
    the stored target. Code's arithmetic (ADR-050)."""
    target = money(line.get("safe_harbor_target"))
    paid_on_time = [
        Decimal(str(p["amount"]))
        for p in payments
        if p["filing_extension_id"] == line["id"]
        and (p["paid_on"] is None or p["paid_on"] <= line["original_due_on"])
    ]
    withheld = money(line.get("withholding_plus_estimates")) or Decimal(0)
    params = _parameters(tax_year)
    if params is None:
        paid = withheld + sum(paid_on_time, Decimal(0))
        return LineCheck(
            return_id,
            str(line["jurisdiction"]),
            money(line.get("projected_liability")),
            None,
            paid,
            None,
            None,
        )
    check = engine.paid_by_original_due(withheld, paid_on_time, target, params)
    return LineCheck(
        return_id,
        str(line["jurisdiction"]),
        money(line.get("projected_liability")),
        check.target,
        check.paid_by_original_due,
        check.meets,
        check.stamp.inputs_hash,
    )


async def on_return(ctx: AuthContext, engagement_id: UUID, return_id: UUID) -> Resource:
    """The engagement with the return as the work item (`function_in` reads it there)."""
    return replace(await engagement_resource(ctx.tenant, engagement_id), work_item_id=return_id)


async def readable_returns(ctx: AuthContext) -> dict[UUID, WorkItemFacts]:
    """The viewer's visible returns, less what an offshore reader may not read: amounts are tax
    return information, so a client without the offshore consent is absent (the matrix's note on
    `filing_extension.read`; DEC-52). Fail closed: no provider, no consent."""
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    if await may_read_unmasked(ctx):
        return facts
    consented = {
        client: await offshore_consented(ctx.tenant, client)
        for client in {f.client_id for f in facts.values()}
    }
    return {k: f for k, f in facts.items() if consented[f.client_id]}


async def rows(ctx: AuthContext, tax_year: int) -> list[ReturnRow]:
    facts = await readable_returns(ctx)
    if not facts:
        return []
    async with tenant_session(ctx.tenant) as session:
        lines = (
            await session.execute(
                text(
                    "SELECT e.*, r.form AS return_form FROM filing_extensions e "
                    "JOIN tax_returns r ON r.work_item_id = e.tax_return_id "
                    "WHERE e.tax_year = :y AND e.tax_return_id = ANY(:ids) "
                    "ORDER BY e.tax_return_id, e.jurisdiction"
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
                    line["tax_return_id"],
                    f.work_item_id,
                    f.engagement_id,
                    f.client_name,
                    tax_year,
                    return_form=str(line["return_form"]),
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


async def row_of(ctx: AuthContext, extension_id: UUID) -> ReturnRow:
    """The visible row that holds the extension; a walled one is not found."""
    async with tenant_session(ctx.tenant) as session:
        tax_year = (
            await session.execute(
                text("SELECT tax_year FROM filing_extensions WHERE id = :id"), {"id": extension_id}
            )
        ).scalar()
    if tax_year is None:
        raise NotFound("filing_extension")
    for row in await rows(ctx, int(tax_year)):
        if any(x["id"] == extension_id for x in row.lines):
            return row
    raise NotFound("filing_extension")


async def _unmet_gates(tenant: TenantContext, engagement_id: UUID) -> list[str]:
    return [g for g in REQUIRED_GATES if not (await gate_fact(tenant, engagement_id, g)).met]


async def blocked_reason(tenant: TenantContext, engagement_id: UUID) -> str | None:
    """TAX-13 c's tooltip key: the engagement can't be extended yet."""
    return "gate_unmet" if await _unmet_gates(tenant, engagement_id) else None


async def _target_columns(
    return_form: str, tax_year: int, liability: Decimal | None
) -> dict[str, object]:
    """The stored safe-harbor columns: code's, with the stamp the CHECK needs beside a target."""
    params = _parameters(tax_year)
    if params is None or liability is None:
        return {"pct": None, "target": None, "version": None, "hash": None}
    try:
        harbor = engine.safe_harbor(return_form, liability, params)
    except LookupError:
        return {"pct": None, "target": None, "version": None, "hash": None}
    return {
        "pct": harbor.pct,
        "target": harbor.target,
        "version": harbor.stamp.engine_version if harbor.target is not None else None,
        "hash": harbor.stamp.inputs_hash if harbor.target is not None else None,
    }


async def _line_for(
    tx: UnitOfWork,
    ctx: AuthContext,
    return_row: Mapping[str, Any],  # Any: a database row
    jurisdiction: str,
    form: str | None,
) -> dict[str, Any]:  # Any: a database row
    """The return's line for a jurisdiction, created from the rules the first time."""
    return_id = return_row["work_item_id"]
    found = (
        (
            await tx.session.execute(
                text(
                    "SELECT * FROM filing_extensions WHERE tax_return_id = :r "
                    "AND jurisdiction = :j FOR UPDATE"
                ),
                {"r": return_id, "j": jurisdiction},
            )
        )
        .mappings()
        .first()
    )
    if found is not None:
        return dict(found)
    dates = await dates_for(
        str(return_row["form"]), int(return_row["tax_year"]), return_row["fiscal_year_end"]
    )
    if dates is None or dates.extended_due_on is None:
        raise NoExtensionForm(facts={"return_id": str(return_id)})
    if jurisdiction == FEDERAL:
        form = dates.extension_form
    elif form is None:
        raise StateFormRequired(facts={"jurisdiction": jurisdiction})
    if form not in EXTENSION_FORMS:
        raise NoExtensionForm(facts={"return_id": str(return_id)})
    versions = dates.reference_set_version_ids
    created = (
        (
            await tx.session.execute(
                text(
                    "INSERT INTO filing_extensions (id, tenant_id, engagement_id, work_item_id, "
                    "tax_return_id, tax_year, jurisdiction, form, original_due_on, "
                    "extended_due_on, due_rules_version_id, created_by) VALUES (:id, :t, :e, :r, "
                    ":r, :y, :j, :form, :orig, :ext, :rules, :by) RETURNING *"
                ),
                {
                    "id": uuid4(),
                    "t": ctx.tenant_id,
                    "e": return_row["engagement_id"],
                    "r": return_id,
                    "y": return_row["tax_year"],
                    "j": jurisdiction,
                    "form": form,
                    "orig": dates.original_due_on,
                    "ext": dates.extended_due_on,
                    "rules": versions[0] if versions else None,
                    "by": ctx.user_id,
                },
            )
        )
        .mappings()
        .one()
    )
    return dict(created)


async def _propose(
    tx: UnitOfWork, ctx: AuthContext, extension_id: UUID, kind: str, amount: Decimal
) -> UUID | None:
    """A proposed payment; a different amount supersedes the live row, the same one is no change
    (a repeat of the same click writes nothing)."""
    live = (
        (
            await tx.session.execute(
                text(
                    "SELECT id, amount FROM extension_payments p WHERE filing_extension_id = :e "
                    "AND kind = :k AND NOT EXISTS (SELECT 1 FROM extension_payments s "
                    "WHERE s.supersedes_id = p.id) FOR UPDATE"
                ),
                {"e": extension_id, "k": kind},
            )
        )
        .mappings()
        .first()
    )
    if live is not None and Decimal(str(live["amount"])) == amount:
        return None
    payment_id = uuid4()
    await tx.session.execute(
        text(
            "INSERT INTO extension_payments (id, tenant_id, filing_extension_id, kind, amount, "
            "proposed_by, supersedes_id) VALUES (:id, :t, :e, :k, :a, :by, :old)"
        ),
        {
            "id": payment_id,
            "t": ctx.tenant_id,
            "e": extension_id,
            "k": kind,
            "a": amount,
            "by": ctx.user_id,
            "old": live["id"] if live is not None else None,
        },
    )
    return payment_id


async def _return_rows(
    session: AsyncSession, return_ids: Sequence[UUID], engagements: Mapping[UUID, UUID]
) -> dict[UUID, dict[str, Any]]:  # Any: database rows
    found = await session.execute(
        text(
            "SELECT work_item_id, form, tax_year, fiscal_year_end FROM tax_returns "
            "WHERE work_item_id = ANY(:ids) FOR UPDATE"
        ),
        {"ids": list(return_ids)},
    )
    return {
        row["work_item_id"]: {**row, "engagement_id": engagements[row["work_item_id"]]}
        for row in found.mappings()
    }


async def _prepare_in(
    tx: UnitOfWork,
    ctx: AuthContext,
    return_ids: Sequence[UUID],
    payments: Sequence[ProposedPayment],
) -> tuple[list[UUID], list[LineCheck]]:
    """Prepare inside the caller's unit of work. Every return is checked before anything is
    written, so one refusal leaves the whole selection as it was."""
    visible = {f.work_item_id: f.engagement_id for f in await work_item_facts(ctx, KIND)}
    wanted = list(dict.fromkeys([*return_ids, *(p.return_id for p in payments)]))
    if any(r not in visible for r in wanted):
        raise NotFound("tax_return")
    found = await _return_rows(tx.session, wanted, visible)
    for return_id in wanted:
        if return_id not in found:
            raise NotFound("tax_return")
        engagement_id = found[return_id]["engagement_id"]
        await authorise(ctx, PREPARE, await on_return(ctx, engagement_id, return_id))
        unmet = await _unmet_gates(ctx.tenant, engagement_id)
        if unmet:
            raise ExtensionGateUnmet(
                facts={"return_id": str(return_id), "gate": unmet[0], "unmet": len(unmet)}
            )
    extension_ids: list[UUID] = []
    checks: list[LineCheck] = []
    for return_id in wanted:
        row = found[return_id]
        mine = [p for p in payments if p.return_id == return_id]
        jurisdictions = list(dict.fromkeys([FEDERAL, *(p.jurisdiction for p in mine)]))
        lines: list[dict[str, Any]] = []  # Any: database rows
        for jurisdiction in jurisdictions:
            form = next((p.form for p in mine if p.jurisdiction == jurisdiction), None)
            line = await _line_for(tx, ctx, row, jurisdiction, form)
            for p in (x for x in mine if x.jurisdiction == jurisdiction):
                await _propose(tx, ctx, line["id"], p.kind, p.amount)
            if line["status"] == "not_filed":
                await tx.session.execute(
                    text(
                        "UPDATE filing_extensions SET status = 'prepared', "
                        "row_version = row_version + 1 WHERE id = :id"
                    ),
                    {"id": line["id"]},
                )
            lines.append(line)
            extension_ids.append(line["id"])
        stored = await tx.session.execute(
            text(
                "SELECT p.* FROM extension_payments p WHERE p.filing_extension_id = ANY(:ids) "
                "AND NOT EXISTS (SELECT 1 FROM extension_payments s WHERE s.supersedes_id = p.id)"
            ),
            {"ids": [x["id"] for x in lines]},
        )
        live = [dict(p) for p in stored.mappings()]
        checks.extend(line_check(return_id, x, live, int(row["tax_year"])) for x in lines)
        tx.record(
            "filing_extension.prepared",
            target=Target("work_item", return_id),
            after=Ref(lines=len(lines), payments=len(mine)),
        )
    return extension_ids, checks


async def prepare(
    ctx: AuthContext, return_ids: Sequence[UUID], payments: Sequence[ProposedPayment]
) -> tuple[list[UUID], list[LineCheck]]:
    async with uow(ctx.tenant) as tx:
        return await _prepare_in(tx, ctx, return_ids, payments)


async def _approve_in(
    tx: UnitOfWork, ctx: AuthContext, extension_ids: Sequence[UUID]
) -> list[Any]:  # Any: database rows
    """Approve every proposed payment on the extensions as the caller, authorised per return."""
    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    pending = list(
        (
            await tx.session.execute(
                text(
                    "SELECT p.id, p.amount, e.tax_return_id, e.jurisdiction, e.form, "
                    "e.original_due_on FROM extension_payments p JOIN filing_extensions e "
                    "ON e.id = p.filing_extension_id WHERE e.id = ANY(:ids) "
                    "AND p.approved_by IS NULL AND NOT EXISTS (SELECT 1 FROM extension_payments s "
                    "WHERE s.supersedes_id = p.id) FOR UPDATE OF p"
                ),
                {"ids": list(extension_ids)},
            )
        ).mappings()
    )
    pending = [p for p in pending if p["tax_return_id"] in visible]
    if not pending:
        raise NothingToApprove
    for return_id in dict.fromkeys(p["tax_return_id"] for p in pending):
        await authorise(
            ctx, APPROVE, await on_return(ctx, visible[return_id].engagement_id, return_id)
        )
    await tx.session.execute(
        text(
            "UPDATE extension_payments SET approved_by = :by, approved_actor_kind = 'human', "
            "approved_at = abacus_now() WHERE id = ANY(:ids)"
        ),
        {"by": ctx.user_id, "ids": [p["id"] for p in pending]},
    )
    for return_id in dict.fromkeys(p["tax_return_id"] for p in pending):
        tx.record(
            "extension_payment.approved",
            target=Target("work_item", return_id),
            after=Ref(payments=sum(1 for p in pending if p["tax_return_id"] == return_id)),
        )
    return pending


async def approve_and_request(
    ctx: AuthContext,
    extension_ids: Sequence[UUID],
    *,
    send_confirmations: bool,
    return_ids: Sequence[UUID] = (),
    payments: Sequence[ProposedPayment] = (),
) -> tuple[list[UUID], list[UUID], list[LineCheck]]:
    """Prepare any named returns, approve as the caller and create one confirmation request per
    return, attributed to the caller, sent, all in one unit of work."""
    from abacus.modules.requests.api import BulkItem, create_items_bulk, send_created

    if send_confirmations:
        # A person sends the confirmation requests; the agent never does (AGENT-001).
        await authorise(ctx, SEND, Resource.firm(ctx.tenant_id))

    created: list[tuple[UUID, UUID]] = []
    async with uow(ctx.tenant) as tx:
        chosen = list(extension_ids)
        checks: list[LineCheck] = []
        if return_ids or payments:
            prepared, checks = await _prepare_in(tx, ctx, return_ids, payments)
            chosen += prepared
        pending = await _approve_in(tx, ctx, chosen)
        if send_confirmations:
            facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
            batch_id = uuid4()
            for return_id in dict.fromkeys(p["tax_return_id"] for p in pending):
                mine = [p for p in pending if p["tax_return_id"] == return_id]
                listed = ", ".join(sorted({str(p["jurisdiction"]) for p in mine}))
                engagement_id = facts[return_id].engagement_id
                ids = await create_items_bulk(
                    tx,
                    ctx,
                    engagement_id,
                    [
                        BulkItem(
                            description=f"Please confirm your extension payments: {listed}"[:2000],
                            audit_area="tax_payments",
                            linked_ref={"type": "tax_return", "id": str(return_id)},
                        )
                    ],
                    wave="year_end",
                    due_on=min(p["original_due_on"] for p in mine),
                    batch_id=batch_id,
                )
                await send_created(tx, ctx, engagement_id, ids[0])
                created.append((engagement_id, ids[0]))
                await _link_confirmation(tx, return_id, ids[0])
    return [p["id"] for p in pending], [item for _, item in created], checks


async def _link_confirmation(tx: UnitOfWork, return_id: UUID, item_id: UUID) -> None:
    await tx.session.execute(
        text(
            "UPDATE filing_extensions SET confirmation_request_item_id = :item, "
            "row_version = row_version + 1 WHERE tax_return_id = :r"
        ),
        {"item": item_id, "r": return_id},
    )


@dataclass(frozen=True)
class ConfirmationSent:
    request_item_id: UUID
    request_list_id: UUID
    sent_at: object
    contact_name: str


async def confirmation_contact(
    ctx: AuthContext, engagement_id: UUID, contact_id: UUID | None
) -> tuple[UUID | None, str]:
    """Who the request goes to: the named contact, else the engagement's first client admin."""
    from abacus.modules.engagements.api import contact_portal_user
    from abacus.modules.identity.api import client_admins, names_of

    user: UUID | None
    if contact_id is not None:
        user = await contact_portal_user(ctx.tenant, engagement_id, contact_id)
        if user is None:
            raise NotFound("contact")
    else:
        admins = await client_admins(ctx.tenant, engagement_id)
        user = admins[0] if admins else None
    if user is None:
        return None, ""
    return user, (await names_of([user])).get(user, "")


async def send_confirmation(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    description: str,
    due_on: date,
    contact_id: UUID | None,
    wave: str,
    linked_ref: dict[str, object],
    link: Callable[[UnitOfWork, UUID], Awaitable[None]] | None = None,
) -> ConfirmationSent:
    """One confirmation request, created in the engagement's binder and sent on the click. The
    wording names jurisdictions and periods, never an amount or a form number: the scope check
    reads any number in client text as an amount."""
    from abacus.modules.requests.api import (
        BulkItem,
        ItemPatch,
        create_items_bulk,
        request_item_sent,
        send_created,
        update_item,
    )

    user, name = await confirmation_contact(ctx, engagement_id, contact_id)
    async with uow(ctx.tenant) as tx:
        ids = await create_items_bulk(
            tx,
            ctx,
            engagement_id,
            [
                BulkItem(
                    description=description[:2000],
                    audit_area="tax_payments",
                    linked_ref=linked_ref,
                )
            ],
            wave=wave,
            due_on=due_on,
            batch_id=uuid4(),
        )
        await send_created(tx, ctx, engagement_id, ids[0])
        if link is not None:
            await link(tx, ids[0])
    if contact_id is not None and user is not None:
        await update_item(ctx, engagement_id, ids[0], ItemPatch({"client_assignee_user_id": user}))
    list_id, sent_at = await request_item_sent(ctx.tenant, ids[0])
    return ConfirmationSent(ids[0], list_id, sent_at, name)


async def request_one(
    ctx: AuthContext, extension_id: UUID, contact_id: UUID | None
) -> ConfirmationSent:
    row = await row_of(ctx, extension_id)
    line = next(x for x in row.lines if x["id"] == extension_id)
    await authorise(ctx, SEND, await on_return(ctx, row.engagement_id, row.tax_return_id))
    listed = str(line["jurisdiction"])

    async def link(tx: UnitOfWork, item_id: UUID) -> None:
        await tx.session.execute(
            text(
                "UPDATE filing_extensions SET confirmation_request_item_id = :item, "
                "row_version = row_version + 1 WHERE id = :id"
            ),
            {"item": item_id, "id": extension_id},
        )
        tx.record(
            "filing_extension.confirmation_requested",
            target=Target("work_item", row.tax_return_id),
            after=Ref(extension=extension_id, item=item_id),
        )

    return await send_confirmation(
        ctx,
        row.engagement_id,
        description=f"Please confirm your extension payment: {listed}",
        due_on=line["original_due_on"],
        contact_id=contact_id,
        wave="year_end",
        linked_ref={"type": "tax_return", "id": str(row.tax_return_id)},
        link=link,
    )


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
    projected_liability: Decimal | None = None,
    projected_liability_source: str | None = None,
    projected_liability_ref: Mapping[str, str] | None = None,
    withholding_plus_estimates: Decimal | None = None,
) -> int:
    """Mark filed (a person's record with evidence), flag likely to extend, or enter the projected
    liability and what was already paid, one or the other; against the row version the caller saw,
    authorised on the return. Returns the extension's tax year."""
    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    text(
                        "SELECT e.*, r.form AS return_form FROM filing_extensions e "
                        "JOIN tax_returns r ON r.work_item_id = e.tax_return_id "
                        "WHERE e.id = :id FOR UPDATE OF e"
                    ),
                    {"id": extension_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None or row["tax_return_id"] not in visible:
            raise NotFound("filing_extension")
        resource = await on_return(
            ctx, visible[row["tax_return_id"]].engagement_id, row["tax_return_id"]
        )
        await authorise(ctx, action, resource)
        # The route declares `mark_filed` (its guard needs that very check); the matrix holds the
        # three edits to the same people, so this refuses nobody the first check let through.
        await authorise(ctx, MARK_FILED, resource)
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
        if projected_liability is not None or withholding_plus_estimates is not None:
            await _set_figures(
                tx,
                dict(row),
                projected_liability,
                projected_liability_source,
                projected_liability_ref,
                withholding_plus_estimates,
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


async def _set_figures(
    tx: UnitOfWork,
    row: Mapping[str, Any],  # Any: a database row
    projected_liability: Decimal | None,
    source: str | None,
    reference: Mapping[str, str] | None,
    withheld: Decimal | None,
) -> None:
    """A preparer's figures with their source; code recomputes the target and its stamp."""
    if projected_liability is not None and (source is None or not reference):
        raise LiabilityNeedsSource
    liability = (
        projected_liability
        if projected_liability is not None
        else money(row["projected_liability"])
    )
    columns = await _target_columns(str(row["return_form"]), int(row["tax_year"]), liability)
    await tx.session.execute(
        text(
            "UPDATE filing_extensions SET projected_liability = :l, "
            "projected_liability_source = coalesce(:src, projected_liability_source), "
            "projected_liability_ref = coalesce(CAST(:ref AS jsonb), projected_liability_ref), "
            "withholding_plus_estimates = coalesce(:w, withholding_plus_estimates), "
            "safe_harbor_pct = :pct, safe_harbor_target = :target, engine_version = :version, "
            "inputs_hash = :hash, row_version = row_version + 1 WHERE id = :id"
        ),
        {
            "l": liability,
            "src": source,
            "ref": json.dumps(reference) if reference else None,
            "w": withheld,
            "id": row["id"],
            **columns,
        },
    )
    tx.record(
        "filing_extension.figures_entered",
        target=Target("work_item", row["tax_return_id"]),
        after=Ref(extension=row["id"]),
    )


# --- submit for approval (DEC-2350) -------------------------------------------------------------


async def submit_for_approval(ctx: AuthContext, extension_ids: Sequence[UUID]) -> list[UUID]:
    """The preparer's path: the return's reviewers are told, and approve through
    approve-and-request. HOME-02's row through C13 is T-03's cut-list item 3 (T-08 / I-01): a
    preparer can't raise a C3 card (`decision_card.raise` is a manager's or senior's), and a card's
    reserved role can't name "any of the reviewer functions". Returns the returns submitted."""
    visible = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            text(
                "SELECT DISTINCT e.tax_return_id FROM extension_payments p "
                "JOIN filing_extensions e ON e.id = p.filing_extension_id WHERE e.id = ANY(:ids) "
                "AND p.approved_by IS NULL AND NOT EXISTS (SELECT 1 FROM extension_payments s "
                "WHERE s.supersedes_id = p.id)"
            ),
            {"ids": list(extension_ids)},
        )
        returns = [r for r in found.scalars() if r in visible]
    if not returns:
        raise NothingToApprove
    for return_id in returns:
        engagement_id = visible[return_id].engagement_id
        await authorise(ctx, PREPARE, await on_return(ctx, engagement_id, return_id))
        async with uow(ctx.tenant) as tx:
            tx.record(
                "filing_extension.submitted_for_approval",
                target=Target("work_item", return_id),
            )
            tx.emit(
                ExtensionApprovalRequested(
                    work_item_id=return_id,
                    engagement_id=engagement_id,
                    by_user=ctx.user_id,
                    recipient_user_ids=[
                        user
                        for function in REVIEWER_FUNCTIONS
                        for user in visible[return_id].assignees.get(function, ())
                    ],
                )
            )
    return returns


# --- TaxCalendarSweep's date half (T-03 US-4.6) ------------------------------------------------


async def recompute_open_lines(tenant: TenantContext) -> int:
    """Every open line against the rules now in effect. A changed date is written with both rule
    versions (`filing_extension.due_date_recomputed`, system actor), never silently; a filed line
    keeps what it was filed under."""
    async with tenant_session(tenant) as session:
        open_lines = list(
            (
                await session.execute(
                    text(
                        "SELECT e.id, e.tax_return_id, e.original_due_on, e.extended_due_on, "
                        "e.due_rules_version_id, r.form, r.tax_year, r.fiscal_year_end "
                        "FROM filing_extensions e JOIN tax_returns r "
                        "ON r.work_item_id = e.tax_return_id "
                        "WHERE e.status IN ('not_filed', 'prepared')"
                    )
                )
            ).mappings()
        )
    changed = 0
    for line in open_lines:
        if str(line["form"]) not in FORM_FOR_RULES:
            continue
        dates = await dates_for(str(line["form"]), int(line["tax_year"]), line["fiscal_year_end"])
        if dates is None or dates.extended_due_on is None:
            continue
        if (dates.original_due_on, dates.extended_due_on) == (
            line["original_due_on"],
            line["extended_due_on"],
        ):
            continue
        versions = dates.reference_set_version_ids
        new_rules = versions[0] if versions else None
        async with uow(tenant) as tx:
            await tx.session.execute(
                text(
                    "UPDATE filing_extensions SET original_due_on = :o, extended_due_on = :x, "
                    "due_rules_version_id = :rules, row_version = row_version + 1 WHERE id = :id"
                ),
                {
                    "o": dates.original_due_on,
                    "x": dates.extended_due_on,
                    "rules": new_rules,
                    "id": line["id"],
                },
            )
            tx.record(
                "filing_extension.due_date_recomputed",
                target=Target("work_item", line["tax_return_id"]),
                before=Ref(rules=cast(UUID, line["due_rules_version_id"])),
                after=Ref(rules=cast(UUID, new_rules)),
            )
        changed += 1
    return changed


async def on_reference_set_published(event: OutboxEvent) -> None:
    await recompute_open_lines(TenantContext(event.tenant_id, "system", "tax:extensions"))


async def on_filing_acknowledged(event: OutboxEvent) -> None:
    """ExtensionAckConsumer: a rejected extension tells the return's preparer and manager."""
    extension_id = event.payload.get("extension_id")
    if extension_id is None or event.payload.get("status") != "rejected":
        return
    from abacus.modules.engagements.api import function_holders

    tenant = TenantContext(event.tenant_id, "system", "tax:extensions")
    work_item_id = UUID(str(event.payload["return_id"]))
    holders = await function_holders(tenant, work_item_id)
    async with uow(tenant) as tx:
        tx.record(
            "filing_extension.ack_rejection_notified",
            target=Target("work_item", work_item_id),
            after=Ref(extension=UUID(str(extension_id))),
        )
        tx.emit(
            ExtensionAckRejected(
                work_item_id=work_item_id,
                engagement_id=UUID(str(event.payload["engagement_id"])),
                extension_id=UUID(str(extension_id)),
                reject_code=str(event.payload.get("reject_code") or ""),
                recipient_user_ids=[
                    user
                    for function in ("preparer", "manager_reviewer")
                    for user in holders.get(function, ())
                ],
            )
        )
