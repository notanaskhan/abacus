"""T-03-T07: extensions (TAX-13 a; T-03 §3 F5; DEC-2243).

- **Rows.** Filing extensions grouped per return, only for returns the viewer may see
  (`engagements.api.work_item_facts`, walls applied), with the counts from those rows alone:
  `{extended, open, filed, likely, acks_pending}` (DEC-43: a walled return is absent, never
  counted).
- **Approve and request.** One unit of work as the caller (a person; the matrix holds the
  reviewer function): every proposed payment on the chosen extensions is approved, then one
  confirmation request item is created per return in its binder's engagement, attributed to the
  caller. A payment is a method label and an amount; no route stores or transmits an instrument.
- **Mark filed** is a person's record (date, form, the filed form's evidence version); Accrued
  never transmits an extension (DEC-49).

Figures (projected liability, the safe-harbor target) are stored by code with their engine stamp
(T-03-T04's `tax.compute.payments`); this module reads them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.identity.api import AuthContext, Resource, authorise

KIND = "tax_return"


class NothingToApprove(DomainConflict):
    """None of the chosen extensions has a proposed payment."""

    code = "nothing_to_approve"


class FiledNeedsEvidence(DomainInvalid):
    """A filed record names the date and the filed form's evidence version."""

    code = "filed_needs_evidence"


class ExtensionMoved(DomainConflict):
    code = "version_conflict"


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
    async with uow(ctx.tenant) as tx:
        pending = list(
            (
                await tx.session.execute(
                    text(
                        "SELECT p.id, p.amount, e.tax_return_id, e.jurisdiction, e.form "
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
    return approved, requested


async def patch(
    ctx: AuthContext,
    extension_id: UUID,
    *,
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
    visible = {f.work_item_id for f in await work_item_facts(ctx, KIND)}
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


def money(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))
