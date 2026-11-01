"""The delivery checklist and packet (T-01-T35; T-01 §3.11; TAX-12 a, b; DEC-38; DEC-1565). RED.

- **Read** (`tax_return.read` on the return): the open packet and its items, and the payment
  instructions read from the return's field values, which the approved engine import wrote
  (engine values only: refund, balance due and next year's estimate per jurisdiction; a zero is
  left out). The 8879 binding, transmission and acknowledgements are T-01-T36/T37's: absent here.
- **Assemble** (`delivery_packet.prepare`: `client_service` or a manager, a person): only after
  final approval and an export. The items are the engine PDFs the bridge filed (client copy,
  Form 8879 with TR-579-IT, the 1040-ES and IT-2105 vouchers) and the filing-instructions letter,
  rendered through C11 from the firm's published `delivery_cover_letter` template with values
  code fills (client, return, signer, date, payments). No model is asked for anything: no text
  of the letter comes from the gateway (ADR P-25 off). A new assembly supersedes the open draft;
  an approved packet is not re-assembled (409 `packet_approved`).
- **Toggle** the vouchers and the invoice, and **regenerate** the letter (a new C11 draft of the
  same document), on a draft at the version seen (409 `stale_version`).
- **Approve** (`delivery_packet.approve`: the return's signer or a manager, DEC-38; a person
  only): the draft becomes approved, audited with the approver; `client_service` cannot.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, RowMapping, TextClause, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    ero_designated,
    names_of,
)
from abacus.modules.methodology.api import (
    current_report_template_version,
    report_templates_in_firm,
)
from abacus.modules.reporting import api as c11
from abacus.modules.review.api import current_values
from abacus.modules.tax.approval import signer_for
from abacus.modules.tax.engine_files import engine_documents
from abacus.modules.tax.filing import (
    ACK_RECORD,
    ISSUE_CREATE,
    TRANSMIT,
    binding_state,
    envelope_of,
)

TARGET: Final = "tax_return"
PACKET: Final = "delivery_packet"
PREPARE: Final = "delivery_packet.prepare"
APPROVE: Final = "delivery_packet.approve"
READ: Final = "tax_return.read"
LETTER_KIND: Final = "delivery_cover_letter"
LETTER_OWNER: Final = "delivery_packet"
# Final approval came first: the return's statuses from approval on (export.EXPORTABLE).
APPROVED: Final = frozenset({"approved", "awaiting_signature", "filed", "accepted"})
# TAX-12 B's order; the engine PDF kind each item takes (the 8879 carries TR-579-IT with it).
ITEMS: Final[tuple[tuple[str, str | None], ...]] = (
    ("client_copy", "client_copy"),
    ("filing_instructions_letter", None),
    ("form_8879_tr_579_it", "form_8879"),
    ("voucher_1040es_q4", "voucher_1040es_q4"),
    ("voucher_it2105_q4", "voucher_it2105_q4"),
    ("engagement_invoice", None),
)
TOGGLEABLE: Final = frozenset({"voucher_1040es_q4", "voucher_it2105_q4", "engagement_invoice"})
# The engine's field prefixes, by jurisdiction (the bridge's values file; tax-engine-bridge §4).
_REFUND: Final = (("US", "f1040.refund"),)
_DUE: Final = (
    ("NY", "it201.balance_due"),
    ("IL", "il1040.balance_due"),
    ("CO", "co_dr0104pn.balance_due"),
)
_ESTIMATES: Final = (
    ("US", "f1040es_{year}.voucher_amount"),
    ("NY", "it2105_{year}.voucher_amount"),
)
_NAMES: Final = {"US": "Federal", "NY": "New York", "IL": "Illinois", "CO": "Colorado"}


class NotFinalApproved(DomainConflict):
    code = "not_final_approved"


class NotExported(DomainConflict):
    code = "not_exported"


class PacketApproved(DomainConflict):
    code = "packet_approved"


class PacketNotDraft(DomainConflict):
    code = "packet_not_draft"


class StaleVersion(DomainConflict):
    code = "stale_version"


class NoLetterTemplate(DomainConflict):
    code = "no_letter_template"


class LetterRefused(DomainConflict):
    code = "letter_refused"


class ItemNotToggleable(DomainConflict):
    code = "item_not_toggleable"


@dataclass(frozen=True)
class Payment:
    jurisdiction: str
    kind: Literal["refund", "balance_due", "estimate"]
    amount: Decimal
    due_on: date | None


@dataclass(frozen=True)
class Item:
    kind: str
    evidence_version_id: UUID | None
    included: bool


@dataclass(frozen=True)
class Packet:
    id: UUID
    return_id: UUID
    version: int
    status: Literal["draft", "approved", "superseded"]
    items: tuple[Item, ...]
    letter_document_id: UUID | None
    approved_by_name: str | None
    row_version: int


@dataclass(frozen=True)
class Delivery:
    return_id: UUID
    packet: Packet | None
    payments: tuple[Payment, ...]
    allowed_actions: tuple[str, ...]
    # T-01-T36: the 8879 envelope and its amount binding (None until drafted).
    envelope_id: UUID | None = None
    binding_id: UUID | None = None
    binding_superseded: bool = False


@dataclass(frozen=True)
class _Return:
    engagement_id: UUID
    client_id: UUID
    client_name: str
    status: str
    tax_year: int
    form: str


async def _return(ctx: AuthContext, return_id: UUID) -> _Return:
    """The return as the viewer may see it (404 otherwise, INV-3), with its tax facts."""
    item = next(
        (
            i
            for i in await work_item_facts(ctx, TARGET, "tax_return.read_metadata")
            if i.work_item_id == return_id
        ),
        None,
    )
    if item is None:
        raise NotFound(TARGET)
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT status, tax_year, form FROM tax_returns WHERE work_item_id = :r"),
                {"r": return_id},
            )
        ).first()
    if row is None:
        raise NotFound(TARGET)
    return _Return(
        item.engagement_id, item.client_id, item.client_name, str(row[0]), int(row[1]), str(row[2])
    )


async def _resource(ctx: AuthContext, facts: _Return, return_id: UUID) -> Resource:
    found = await engagement_resource(ctx.tenant, facts.engagement_id)
    return replace(found, client_id=facts.client_id, work_item_id=return_id)


async def _allowed(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


def _person(ctx: AuthContext, action: str) -> None:
    """A live person only: the agent, the system and support never prepare or approve."""
    if ctx.client:
        raise NotFound(TARGET)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _amount(values: Mapping[str, Mapping[str, object]], key: str) -> Decimal | None:
    found = values.get(key)
    if found is None:
        return None
    try:
        return Decimal(str(found.get("v")))
    except (InvalidOperation, TypeError):
        return None


def payments_of(values: Mapping[str, Mapping[str, object]], tax_year: int) -> tuple[Payment, ...]:
    """The engine's refund, balances due and next year's Q4 estimates, in that order; a value the
    engine did not send, or a zero, is left out. Code reads them; nothing is summed."""
    out: list[Payment] = []
    for jurisdiction, key in _REFUND:
        amount = _amount(values, key)
        if amount:
            out.append(Payment(jurisdiction, "refund", amount, None))
    for jurisdiction, key in _DUE:
        amount = _amount(values, key)
        if amount:
            out.append(Payment(jurisdiction, "balance_due", amount, None))
    for jurisdiction, pattern in _ESTIMATES:
        amount = _amount(values, pattern.format(year=tax_year + 1))
        if amount:
            out.append(Payment(jurisdiction, "estimate", amount, None))
    return tuple(out)


def _items(raw: object) -> tuple[Item, ...]:
    out: list[Item] = []
    for entry in cast(list[dict[str, object]], raw or []):
        ev = entry.get("evidence_version_id")
        out.append(
            Item(
                str(entry["kind"]), None if ev is None else UUID(str(ev)), bool(entry["included"])
            )
        )
    return tuple(out)


def _items_json(items: tuple[Item, ...]) -> str:
    return json.dumps(
        [
            {
                "kind": i.kind,
                "evidence_version_id": None
                if i.evidence_version_id is None
                else str(i.evidence_version_id),
                "included": i.included,
            }
            for i in items
        ]
    )


_BY_ID: Final = text(
    "SELECT id, return_id, version, status, items, letter_document_id, approved_by, row_version "
    "FROM delivery_packets WHERE id = :v"
)
_OPEN_FOR_RETURN: Final = text(
    "SELECT id, return_id, version, status, items, letter_document_id, approved_by, row_version "
    "FROM delivery_packets WHERE return_id = :v AND status <> 'superseded' "
    "ORDER BY version DESC LIMIT 1"
)


async def _packet_row(
    tenant: TenantContext, statement: TextClause, value: UUID
) -> RowMapping | None:
    async with tenant_session(tenant) as session:
        return (await session.execute(statement, {"v": value})).mappings().first()


async def _packet_of(row: RowMapping) -> Packet:
    approver = cast(UUID | None, row["approved_by"])
    names = await names_of([approver]) if approver is not None else {}
    return Packet(
        id=cast(UUID, row["id"]),
        return_id=cast(UUID, row["return_id"]),
        version=int(row["version"]),
        status=cast(Literal["draft", "approved", "superseded"], str(row["status"])),
        items=_items(row["items"]),
        letter_document_id=cast(UUID | None, row["letter_document_id"]),
        approved_by_name=None if approver is None else names.get(approver),
        row_version=int(row["row_version"]),
    )


async def _reread(ctx: AuthContext, packet_id: UUID) -> Packet:
    row = await _packet_row(ctx.tenant, _BY_ID, packet_id)
    if row is None:
        raise NotFound(PACKET)
    return await _packet_of(row)


async def _open(tenant: TenantContext, return_id: UUID) -> RowMapping | None:
    return await _packet_row(tenant, _OPEN_FOR_RETURN, return_id)


async def delivery(ctx: AuthContext, return_id: UUID) -> Delivery:
    facts = await _return(ctx, return_id)
    resource = await _resource(ctx, facts, return_id)
    try:
        await authorise(ctx, READ, resource)
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound(TARGET) from None
        raise
    row = await _open(ctx.tenant, return_id)
    packet = None if row is None else await _packet_of(row)
    values = await current_values(ctx.tenant, TARGET, return_id)
    allowed: list[str] = []
    person = ctx.tenant.actor_kind == "human" and not ctx.is_support
    if person and facts.status in APPROVED and await _allowed(ctx, PREPARE, resource):
        allowed.append(PREPARE)
    if (
        person
        and packet is not None
        and packet.status == "draft"
        and await _allowed(ctx, APPROVE, resource)
    ):
        allowed.append(APPROVE)
    # T-01-T37: the designated ERO on the return records the transmission; the reviewers and
    # client service enter an acknowledgement (the service re-checks every condition).
    if (
        person
        and facts.status in ("approved", "awaiting_signature")
        and await ero_designated(ctx.tenant, ctx.user_id)
        and await _allowed(ctx, TRANSMIT, resource)
    ):
        allowed.append(TRANSMIT)
    if (
        person
        and facts.status in ("filed", "rejected")
        and await _allowed(ctx, ACK_RECORD, resource)
    ):
        allowed.append(ACK_RECORD)
    # Create issue on a rejection needs `issue.create` too, which client service does not hold.
    if (
        person
        and facts.status == "rejected"
        and ACK_RECORD in allowed
        and await _allowed(ctx, ISSUE_CREATE, resource)
    ):
        allowed.append(ISSUE_CREATE)
    binding_id, superseded = await binding_state(ctx.tenant, return_id)
    return Delivery(
        return_id,
        packet,
        payments_of(values, facts.tax_year),
        tuple(allowed),
        envelope_id=None if binding_id is None else await envelope_of(ctx.tenant, binding_id),
        binding_id=binding_id,
        binding_superseded=superseded,
    )


# --- the filing-instructions letter (C11) -----------------------------------------------------

_resolving: ContextVar[Mapping[UUID, Mapping[str, str]] | None] = ContextVar(
    "abacus_delivery_letter_variables", default=None
)


async def _provider(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
    """The values this call resolved for the packet (an unresolved owner gets nothing)."""
    current = _resolving.get()
    if current is None or owner.type != LETTER_OWNER:
        return {}
    return current.get(owner.id, {})


async def _no_approval(ref: c11.ApprovalRef) -> tuple[UUID, str] | None:
    return None  # the letter is delivered as approved within its packet, never finalised alone


def ensure_kind() -> None:
    try:
        c11.document_kind(LETTER_KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=LETTER_KIND,
                layout="letter",
                variables_provider=_provider,
                approval_provider=_no_approval,
                retention_record_type="tax_return",
                formats=("pdf",),
            )
        )


def _money(amount: Decimal) -> str:
    return f"${amount:,.0f}" if amount == amount.to_integral() else f"${amount:,.2f}"


def _payments_line(payments: tuple[Payment, ...]) -> str:
    words = {"refund": "refund", "balance_due": "balance due", "estimate": "Q4 estimate"}
    parts = [
        f"{_NAMES.get(p.jurisdiction, p.jurisdiction)} {words[p.kind]} {_money(p.amount)}"
        for p in payments
    ]
    return " · ".join(parts) if parts else "No payment is due"


def _long_date(on: date) -> str:
    return f"{on:%B} {on.day}, {on.year}"


async def _letter_values(
    ctx: AuthContext, facts: _Return, payments: tuple[Payment, ...]
) -> dict[str, str]:
    signer = await signer_for(ctx.tenant_id, facts.client_id)
    names = await names_of([signer]) if signer is not None else {}
    on = await today(ctx.tenant)
    return {
        "letter.date": _long_date(on),
        "client.name": facts.client_name,
        "return.label": f"{facts.tax_year} Form {facts.form}",
        "firm.signer": names.get(signer, "") if signer is not None else "",
        "payments.summary": _payments_line(payments),
    }


async def _template_version(ctx: AuthContext) -> UUID:
    for template in await report_templates_in_firm(ctx, LETTER_KIND):
        if template.current_version is not None:
            version = await current_report_template_version(ctx.tenant, template.id)
            if version is not None:
                return version
    raise NoLetterTemplate("no published filing-instructions template")


async def _render_letter(
    tx: UnitOfWork,
    ctx: AuthContext,
    packet_id: UUID,
    facts: _Return,
    values: Mapping[str, str],
    template_version_id: UUID,
) -> UUID:
    ensure_kind()
    token = _resolving.set({packet_id: dict(values)})
    try:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind=LETTER_KIND,
                owner_ref=c11.OwnerRef(LETTER_OWNER, packet_id),
                scope=c11.RenderScope(
                    client_id=facts.client_id, engagement_id=facts.engagement_id
                ),
                template_version_id=template_version_id,
                requested_by=c11.Requester("human", user_id=ctx.user_id),
            ),
        )
    except c11.RenderRefused as refused:
        raise LetterRefused(refused.code) from None
    finally:
        _resolving.reset(token)
    return ticket.generated_document_id


# --- writes -----------------------------------------------------------------------------------


async def _items_now(ctx: AuthContext, return_id: UUID) -> tuple[Item, ...]:
    out: list[Item] = []
    for kind, engine_kind in ITEMS:
        if engine_kind is None:
            out.append(Item(kind, None, kind != "engagement_invoice"))
            continue
        found = await engine_documents(ctx.tenant, return_id, engine_kind)
        out.append(Item(kind, found[0] if found else None, bool(found)))
    return tuple(out)


async def _exported(tenant: TenantContext, return_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT 1 FROM engine_exports WHERE return_id = :r LIMIT 1"), {"r": return_id}
        )
    return found is not None


async def assemble(ctx: AuthContext, return_id: UUID) -> Packet:
    _person(ctx, PREPARE)
    facts = await _return(ctx, return_id)
    resource = await _resource(ctx, facts, return_id)
    await authorise(ctx, PREPARE, resource)
    if facts.status not in APPROVED:
        raise NotFinalApproved(facts={"work_item_id": str(return_id)})
    if not await _exported(ctx.tenant, return_id):
        raise NotExported(facts={"work_item_id": str(return_id)})
    template_version = await _template_version(ctx)
    items = await _items_now(ctx, return_id)
    values = await current_values(ctx.tenant, TARGET, return_id)
    letter_values = await _letter_values(ctx, facts, payments_of(values, facts.tax_year))
    packet_id = uuid4()
    async with uow(ctx.tenant) as tx:
        current = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, version, status FROM delivery_packets WHERE return_id = :r "
                        "ORDER BY version DESC LIMIT 1 FOR UPDATE"
                    ),
                    {"r": return_id},
                )
            )
            .mappings()
            .first()
        )
        if current is not None and current["status"] == "approved":
            raise PacketApproved(facts={"packet_id": str(current["id"])})
        if current is not None and current["status"] == "draft":
            await tx.session.execute(
                text(
                    "UPDATE delivery_packets SET status = 'superseded', "
                    "row_version = row_version + 1 WHERE id = :id"
                ),
                {"id": current["id"]},
            )
        version = 1 if current is None else int(current["version"]) + 1
        await tx.session.execute(
            text(
                "INSERT INTO delivery_packets (id, tenant_id, return_id, version, items, "
                "prepared_by) VALUES (:id, :t, :r, :n, CAST(:items AS jsonb), :by)"
            ),
            {
                "id": packet_id,
                "t": ctx.tenant_id,
                "r": return_id,
                "n": version,
                "items": _items_json(items),
                "by": ctx.user_id,
            },
        )
        document_id = await _render_letter(
            tx, ctx, packet_id, facts, letter_values, template_version
        )
        await tx.session.execute(
            text("UPDATE delivery_packets SET letter_document_id = :d WHERE id = :id"),
            {"d": document_id, "id": packet_id},
        )
        tx.record(
            "delivery_packet.assembled",
            target=Target(PACKET, packet_id),
            after=Ref(return_id=return_id, version=version, letter=document_id),
            scope=Scope(engagement_id=facts.engagement_id, client_id=facts.client_id),
        )
    return await _reread(ctx, packet_id)


async def _draft_for(ctx: AuthContext, packet_id: UUID, action: str) -> tuple[RowMapping, _Return]:
    _person(ctx, action)
    row = await _packet_row(ctx.tenant, _BY_ID, packet_id)
    if row is None:
        raise NotFound(PACKET)
    return_id = cast(UUID, row["return_id"])
    facts = await _return(ctx, return_id)
    await authorise(ctx, action, await _resource(ctx, facts, return_id))
    if row["status"] != "draft":
        raise PacketNotDraft(facts={"packet_id": str(packet_id)})
    return row, facts


_SET_ITEMS: Final = text(
    "UPDATE delivery_packets SET items = CAST(:items AS jsonb), row_version = row_version + 1 "
    "WHERE id = :id AND row_version = :seen AND status = 'draft'"
)
_SET_LETTER: Final = text(
    "UPDATE delivery_packets SET letter_document_id = :d, row_version = row_version + 1 "
    "WHERE id = :id AND row_version = :seen AND status = 'draft'"
)
_SET_APPROVED: Final = text(
    "UPDATE delivery_packets SET status = 'approved', approved_by = :by, "
    "approved_at = abacus_now(), row_version = row_version + 1 "
    "WHERE id = :id AND row_version = :seen AND status = 'draft'"
)


async def _bump(
    session: AsyncSession, packet_id: UUID, seen: int, statement: TextClause, **params: object
) -> None:
    """One of the fixed updates, on the draft at the version seen (409 `stale_version`)."""
    moved = await session.execute(statement, {"id": packet_id, "seen": seen, **params})
    if cast(CursorResult[object], moved).rowcount != 1:
        raise StaleVersion(facts={"packet_id": str(packet_id)})


async def toggle(
    ctx: AuthContext, packet_id: UUID, included: Mapping[str, bool], seen_version: int
) -> Packet:
    row, facts = await _draft_for(ctx, packet_id, PREPARE)
    items = list(_items(row["items"]))
    kinds = {i.kind for i in items}
    for kind in included:
        if kind not in TOGGLEABLE or kind not in kinds:
            raise ItemNotToggleable(facts={"kind": kind[:40]})
    changed = tuple(
        replace(i, included=included[i.kind]) if i.kind in included else i for i in items
    )
    async with uow(ctx.tenant) as tx:
        await _bump(
            tx.session,
            packet_id,
            seen_version,
            _SET_ITEMS,
            items=_items_json(changed),
        )
        tx.record(
            "delivery_packet.edited",
            target=Target(PACKET, packet_id),
            after=Ref(version=int(row["version"])),
            scope=Scope(engagement_id=facts.engagement_id, client_id=facts.client_id),
        )
    return await _reread(ctx, packet_id)


async def regenerate_letter(ctx: AuthContext, packet_id: UUID, seen_version: int) -> Packet:
    row, facts = await _draft_for(ctx, packet_id, PREPARE)
    return_id = cast(UUID, row["return_id"])
    template_version = await _template_version(ctx)
    values = await current_values(ctx.tenant, TARGET, return_id)
    letter_values = await _letter_values(ctx, facts, payments_of(values, facts.tax_year))
    async with uow(ctx.tenant) as tx:
        document_id = await _render_letter(
            tx, ctx, packet_id, facts, letter_values, template_version
        )
        await _bump(tx.session, packet_id, seen_version, _SET_LETTER, d=document_id)
        tx.record(
            "delivery_packet.letter_regenerated",
            target=Target(PACKET, packet_id),
            after=Ref(version=int(row["version"]), letter=document_id),
            scope=Scope(engagement_id=facts.engagement_id, client_id=facts.client_id),
        )
    return await _reread(ctx, packet_id)


async def approve(ctx: AuthContext, packet_id: UUID, seen_version: int) -> Packet:
    """DEC-38: the return's signer or a manager-level person approves; a person only."""
    row, facts = await _draft_for(ctx, packet_id, APPROVE)
    async with uow(ctx.tenant) as tx:
        await _bump(
            tx.session,
            packet_id,
            seen_version,
            _SET_APPROVED,
            by=ctx.user_id,
        )
        tx.record(
            "delivery_packet.approved",
            target=Target(PACKET, packet_id),
            after=Ref(version=int(row["version"]), approver=ctx.user_id),
            scope=Scope(engagement_id=facts.engagement_id, client_id=facts.client_id),
        )
    return await _reread(ctx, packet_id)


__all__ = [
    "Delivery",
    "Item",
    "Packet",
    "Payment",
    "approve",
    "assemble",
    "delivery",
    "ensure_kind",
    "payments_of",
    "regenerate_letter",
    "toggle",
]
