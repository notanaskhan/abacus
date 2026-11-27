"""The 1099 / W-9 tracker's backend (C-02-T45; TASK-9003; C-02 F9 US-9.1; CLS-13; DEC-6009;
amber).

- **Rollups** (`VendorRollupConsumer`, on `ledger_snapshot.recorded`): the snapshot's vendor pages
  (connections' reader through `kernel.vendor_pages`, read only) give each QuickBooks vendor a
  `vendors_1099` row for the entity (name from the ledger; a person's classification is never
  overwritten) and its payments by tax year and method (`vendor_payment_rollups`, recomputed: a
  method the year's pages no longer show goes to zero). A year's pages are year to date, so each
  pull replaces the years it covers. The system actor writes; nothing a person decided moves.
- **Tracker** (`tracker`, `GET …/information-returns`): the year's vendors with what code makes
  them (`compute.information_returns.classify`, ADR-050), the tiles, and the rule text from C21's
  rows (DEC-76): the year's threshold, the processor exclusion and the IRIS due date. No number
  or date here is a code constant; a missing threshold answers 503 (DEC-85), a missing due-date
  rule leaves the due text empty.
- **Edits** (`update_vendor`, `PATCH /v1/vendors/{id}`): a person's entity type, attorney flag,
  exemption and rents (`paid_rents`), at the version they saw (409 `stale_version`); the source
  becomes `person`. An agent never edits (its classification is a suggestion a person adopts,
  `vendor_screen.apply_vendor_classification`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound, ServiceUnavailable
from abacus.kernel.uow import MissingAuditEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.closes.compute import information_returns as irc
from abacus.modules.closes.delivery_contract import (
    BatchStatus,
    DeliveryInformationReturnsOut,
    DeliveryVendorPatchIn,
    DeliveryVendorPaymentOut,
    DeliveryVendorRowOut,
    W9Status,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

ROLLUP_ACTOR: Final = "closes:vendor_rollups"
METHODS: Final = ("check", "ach", "card", "payment_app", "other")
# The parser's methods to the rollup's: cash is neither a processor payment nor a check.
_METHOD_OF: Final = {"check": "check", "ach": "ach", "card": "card", "cash": "other"}


class StaleVendor(DomainConflict):
    code = "stale_version"


def rollup_method(method: str) -> str:
    return _METHOD_OF.get(method, "other")


# --- rollups -------------------------------------------------------------------------------------

_UPSERT_VENDOR: Final = text(
    "INSERT INTO vendors_1099 (tenant_id, client_entity_id, external_vendor_id, display_name) "
    "VALUES (:t, :e, :x, :name) ON CONFLICT (tenant_id, client_entity_id, external_vendor_id) "
    "DO UPDATE SET display_name = EXCLUDED.display_name WHERE vendors_1099.display_name "
    "IS DISTINCT FROM EXCLUDED.display_name RETURNING id"
)
_VENDOR_IDS: Final = text(
    "SELECT external_vendor_id, id FROM vendors_1099 WHERE client_entity_id = :e"
)
_UPSERT_ROLLUP: Final = text(
    "INSERT INTO vendor_payment_rollups (tenant_id, client_entity_id, vendor_id, tax_year, "
    "method, amount, txn_count, source_snapshot_id) VALUES (:t, :e, :v, :y, :m, :a, :n, :s) "
    "ON CONFLICT (tenant_id, vendor_id, tax_year, method) DO UPDATE SET amount = EXCLUDED.amount, "
    "txn_count = EXCLUDED.txn_count, source_snapshot_id = EXCLUDED.source_snapshot_id, "
    "computed_at = abacus_now()"
)


@dataclass(frozen=True)
class Rolled:
    vendor_external_id: str
    tax_year: int
    method: str
    amount: Decimal
    txn_count: int


def roll_up(payments: list[tuple[str, date, Decimal, str]]) -> list[Rolled]:
    """Code's rollup (ADR-050): (vendor, txn date, amount, parser method) to totals per vendor,
    payment year and rollup method, every method of each covered vendor-year present (zero when
    unpaid that way), sorted."""
    totals: dict[tuple[str, int, str], tuple[Decimal, int]] = defaultdict(
        lambda: (Decimal("0.00"), 0)
    )
    covered: set[tuple[str, int]] = set()
    for vendor, on, amount, method in payments:
        key = (vendor, on.year, rollup_method(method))
        total, count = totals[key]
        totals[key] = (total + amount, count + 1)
        covered.add((vendor, on.year))
    out: list[Rolled] = []
    for vendor, year in sorted(covered):
        for method in METHODS:
            total, count = totals.get((vendor, year, method), (Decimal("0.00"), 0))
            out.append(Rolled(vendor, year, method, total.quantize(Decimal("0.01")), count))
    return out


async def on_ledger_snapshot_recorded(event: OutboxEvent) -> None:
    """VendorRollupConsumer: the snapshot's vendor pages to vendors and rollups."""
    from abacus.kernel.vendor_pages import vendor_pages_of

    entity, snapshot = event.payload.get("client_entity_id"), event.payload.get("snapshot_id")
    if entity is None or snapshot is None:
        return
    entity_id, snapshot_id = UUID(str(entity)), UUID(str(snapshot))
    tenant = TenantContext(event.tenant_id, "system", ROLLUP_ACTOR)
    found = await vendor_pages_of(tenant, snapshot_id)
    if found.empty:
        return
    names = {v.external_id: v.name for v in found.vendors}
    for p in found.payments:  # a payment to a vendor the page did not list still has a row
        names.setdefault(p.vendor_external_id, p.vendor_external_id)
    rolled = roll_up(
        [(p.vendor_external_id, p.txn_date, p.amount, p.method) for p in found.payments]
    )
    try:
        async with uow(tenant) as tx:
            changed = 0
            for external_id, name in sorted(names.items()):
                made = await tx.session.scalar(
                    _UPSERT_VENDOR,
                    {"t": event.tenant_id, "e": entity_id, "x": external_id, "name": name[:300]},
                )
                changed += made is not None
            ids = {
                str(r.external_vendor_id): cast(UUID, r.id)
                for r in await tx.session.execute(_VENDOR_IDS, {"e": entity_id})
            }
            for r in rolled:
                await tx.session.execute(
                    _UPSERT_ROLLUP,
                    {"t": event.tenant_id, "e": entity_id, "v": ids[r.vendor_external_id],
                     "y": r.tax_year, "m": r.method, "a": r.amount, "n": r.txn_count,
                     "s": snapshot_id},
                )  # fmt: skip
            tx.record(
                "vendor_payments.rolled_up",
                target=Target("ledger_snapshot", snapshot_id),
                after=Ref(vendors=len(names), rollups=len(rolled), renamed=changed),
            )
    except MissingAuditEvent:  # pragma: no cover - the record above always lands
        pass


# --- the tracker ---------------------------------------------------------------------------------

_ENGAGEMENT: Final = text(
    "SELECT engagement_id FROM closes WHERE client_entity_id = :e ORDER BY period DESC LIMIT 1"
)
_YEAR_ROWS: Final = text(
    "SELECT v.id, v.display_name, v.entity_type, v.is_attorney, v.exempt_reason, v.paid_rents, "
    "v.tin_last4, v.w9_status, v.version, r.method, r.amount, r.txn_count, v.tin_kind, "
    "v.backup_withholding, v.w9_evidence_version_id, "
    "(SELECT max(q.sent_at) FROM w9_requests q WHERE v.id = ANY(q.vendor_ids)) AS requested_at, "
    "(SELECT max(m.checked_on) FROM tin_match_results m WHERE m.vendor_id = v.id "
    "AND m.result = 'mismatch') AS mismatch_on "
    "FROM vendors_1099 v JOIN vendor_payment_rollups r ON r.vendor_id = v.id "
    "WHERE v.client_entity_id = :e AND r.tax_year = :y ORDER BY v.display_name, v.id, r.method"
)
_BATCH: Final = text(  # one batch per entity and year (1013's UNIQUE)
    "SELECT id, status, filed_on, ack_at FROM information_return_batches "
    "WHERE client_entity_id = :e AND tax_year = :y"
)
# C-02-T47 (CLS-13 a, d): approval opens after the year's December close locks (the same rule
# `approve_batch` enforces with 409 `close_not_locked`); its due date is the target shown.
_DECEMBER: Final = text(
    "SELECT status, due_on FROM closes WHERE client_entity_id = :e AND period = :p"
)
# C-02-T47 (CLS-13 e): a year whose payments never synced shows the returns it filed.
_FILED_ROWS: Final = text(
    "SELECT v.id, v.display_name, v.entity_type, v.is_attorney, v.tin_last4, v.tin_kind, "
    "v.w9_status, v.version, r.form, r.box, r.amount FROM information_returns r "
    "JOIN vendors_1099 v ON v.id = r.vendor_id WHERE r.batch_id = :b ORDER BY v.display_name, v.id"
)
_FILED: Final = text(
    "SELECT count(DISTINCT vendor_id) FROM information_returns WHERE batch_id = :b"
)
_FILED_VENDORS: Final = text(
    "SELECT DISTINCT vendor_id FROM information_returns WHERE batch_id = :b"
)


async def _entity_engagement(ctx: AuthContext, client_entity_id: UUID, action: str) -> UUID:
    """The entity's close engagement, `action` authorised on it (none, unknown or walled: 404)."""
    from abacus.modules.engagements.api import get_ref

    async with tenant_session(ctx.tenant) as session:
        engagement_id = await session.scalar(_ENGAGEMENT, {"e": client_entity_id})
    if engagement_id is None:
        raise NotFound("client_entity")
    try:
        await authorise(ctx, action, (await get_ref(ctx, cast(UUID, engagement_id))).resource())
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("client_entity") from None
        raise
    return cast(UUID, engagement_id)


def _money(value: Decimal) -> str:
    return f"${value:,.0f}" if value == value.to_integral_value() else f"${value:,.2f}"


async def rule_texts(tax_year: int) -> tuple[irc.Threshold, str, str]:
    """C21's rows for the payment year: the threshold and both summary lines (DEC-76)."""
    from abacus.modules.platform.api import information_return_threshold
    from abacus.modules.tax.api import due_dates_for

    try:
        found = await information_return_threshold("nec", tax_year)
    except LookupError:
        raise ServiceUnavailable("information_return_thresholds") from None
    threshold = irc.Threshold(Decimal(found.threshold_usd), found.min_transactions)
    threshold_rule = (
        f"threshold {_money(threshold.threshold_usd)} for {tax_year} payments (rules table) · "
        "card and payment-app payments excluded (reported on Form 1099-K)"
    )
    try:
        due = await due_dates_for("1099-NEC", tax_year, date(tax_year, 12, 31))
        on = due.original_due_on
        due_rule = (
            f"Recipient copies and 1099-NEC to the IRS due {on:%b} {on.day}, {on.year} · IRIS"
        )
    except LookupError:
        due_rule = ""  # no published rule: the line shows nothing rather than a made-up date
    return threshold, threshold_rule, due_rule


@dataclass
class _Row:
    vendor_id: UUID
    display_name: str
    entity_type: str
    is_attorney: bool
    exempt_reason: str | None
    paid_rents: bool
    tin_last4: str | None
    w9_status: str
    version: int
    payments: list[irc.Payment]
    tin_kind: str | None = None
    backup_withholding: str = "none"
    w9_evidence_version_id: UUID | None = None
    requested_at: datetime | None = None
    mismatch_on: date | None = None


async def tracker(
    ctx: AuthContext, client_entity_id: UUID, tax_year: int, w9: W9Status | None = None
) -> DeliveryInformationReturnsOut:
    """CLS-13 a (and e for a prior year, f when nothing synced)."""
    await _entity_engagement(ctx, client_entity_id, "information_returns.read")
    async with tenant_session(ctx.tenant) as session:
        lines = list(await session.execute(_YEAR_ROWS, {"e": client_entity_id, "y": tax_year}))
        batch = (await session.execute(_BATCH, {"e": client_entity_id, "y": tax_year})).first()
        filed = 0 if batch is None else int(await session.scalar(_FILED, {"b": batch.id}) or 0)
        december = (
            await session.execute(_DECEMBER, {"e": client_entity_id, "p": f"{tax_year}-12"})
        ).first()
        in_batch: set[UUID] = (
            set()
            if batch is None
            else {cast(UUID, v) for v in await session.scalars(_FILED_VENDORS, {"b": batch.id})}
        )
    rows: dict[UUID, _Row] = {}
    for r in lines:
        row = rows.get(r.id)
        if row is None:
            row = rows[r.id] = _Row(
                r.id, str(r.display_name), str(r.entity_type), bool(r.is_attorney),
                r.exempt_reason, bool(r.paid_rents), r.tin_last4, str(r.w9_status),
                int(r.version), [], r.tin_kind, str(r.backup_withholding),
                r.w9_evidence_version_id, r.requested_at, r.mismatch_on,
            )  # fmt: skip
        if Decimal(r.amount) > 0:
            row.payments.append(irc.Payment(str(r.method), Decimal(r.amount), int(r.txn_count)))
    paid = [row for row in rows.values() if row.payments]
    threshold, threshold_rule, due_rule = await rule_texts(tax_year)
    if not paid and batch is not None:
        return await _filed_year(ctx, tax_year, batch, threshold_rule, due_rule, w9)
    items: list[DeliveryVendorRowOut] = []
    reportable = 0
    for row in paid:
        found = irc.classify(
            irc.VendorFacts(row.entity_type, row.is_attorney, row.exempt_reason, row.paid_rents),
            row.payments,
            threshold,
        )
        reportable += found.reportability == "reportable"
        items.append(
            DeliveryVendorRowOut(
                vendor_id=row.vendor_id,
                display_name=row.display_name,
                entity_type=cast(irc.EntityType, row.entity_type),
                is_attorney=row.is_attorney,
                reportability=found.reportability,
                form=found.form,
                box=found.box,
                amount=found.amount,
                tin_last4=row.tin_last4,
                w9_status=cast(irc.W9Status, row.w9_status),
                version=row.version,
                tin_kind=cast(Literal["ssn", "ein"] | None, row.tin_kind),
                backup_withholding=cast(
                    Literal["none", "watch", "started"], row.backup_withholding
                ),
                w9_requested_at=row.requested_at if row.w9_status == "requested" else None,
                w9_evidence_version_id=row.w9_evidence_version_id,
                tin_mismatch_on=row.mismatch_on if row.w9_status == "tin_mismatch" else None,
                filed=row.vendor_id in in_batch,
                payments=[
                    DeliveryVendorPaymentOut(
                        method=cast(
                            Literal["check", "ach", "card", "payment_app", "other"], p.method
                        ),
                        amount=p.amount,
                        txn_count=p.txn_count,
                        counted=p.method not in ("card", "payment_app"),
                    )
                    for p in row.payments
                ],
            )
        )
    shown = [i for i in items if w9 is None or i.w9_status == w9]
    return DeliveryInformationReturnsOut(
        tax_year=tax_year,
        vendors_paid=len(paid),
        reportable=reportable,
        requested=sum(1 for r in paid if r.w9_status == "requested"),
        w9_mismatches=sum(1 for r in paid if r.w9_status == "tin_mismatch"),
        filed=filed if batch is not None and batch.status in ("filed_iris", "accepted") else 0,
        threshold_rule=threshold_rule,
        due_rule=due_rule,
        items=shown,
        batch_status=cast(BatchStatus, "not_started" if batch is None else batch.status),
        filed_on=None if batch is None else batch.filed_on,
        accepted_at=None if batch is None or batch.status != "accepted" else batch.ack_at,
        approval_open=december is not None and december.status == "locked",
        approval_target_on=None if december is None else december.due_on,
    )


async def _filed_year(
    ctx: AuthContext,
    tax_year: int,
    batch: Any,  # noqa: ANN401 # Any: a SQL row (id, status, filed_on, ack_at)
    threshold_rule: str,
    due_rule: str,
    w9: W9Status | None,
) -> DeliveryInformationReturnsOut:
    """CLS-13 e: a prior year filed before the ledger connected (its payments never synced):
    the filed returns, each Reportable, with no Vendors paid figure (`payments_synced` false)."""
    async with tenant_session(ctx.tenant) as session:
        filed = list(await session.execute(_FILED_ROWS, {"b": batch.id}))
    items = [
        DeliveryVendorRowOut(
            vendor_id=r.id, display_name=str(r.display_name),
            entity_type=cast(irc.EntityType, r.entity_type), is_attorney=bool(r.is_attorney),
            reportability="reportable", form=cast(Literal["nec", "misc"], r.form), box=r.box,
            amount=r.amount, tin_last4=r.tin_last4,
            tin_kind=cast(Literal["ssn", "ein"] | None, r.tin_kind),
            w9_status=cast(irc.W9Status, r.w9_status), version=int(r.version), filed=True,
        )
        for r in filed
    ]  # fmt: skip
    return DeliveryInformationReturnsOut(
        tax_year=tax_year,
        vendors_paid=0,
        reportable=len(items),
        requested=0,
        w9_mismatches=0,
        filed=len(items) if batch.status in ("filed_iris", "accepted") else 0,
        threshold_rule=threshold_rule,
        due_rule=due_rule,
        items=[i for i in items if w9 is None or i.w9_status == w9],
        batch_status=cast(BatchStatus, batch.status),
        payments_synced=False,
        filed_on=batch.filed_on,
        accepted_at=batch.ack_at if batch.status == "accepted" else None,
    )


# --- a person's classification -------------------------------------------------------------------

_VENDOR: Final = text(
    "SELECT client_entity_id, entity_type, is_attorney, exempt_reason, paid_rents, version "
    "FROM vendors_1099 WHERE id = :v"
)
_EDIT: Final = text(
    "UPDATE vendors_1099 SET entity_type = :type, is_attorney = :attorney, exempt_reason = "
    ":exempt, paid_rents = :rents, entity_type_source = 'person', updated_by = :by, "
    "updated_at = abacus_now(), version = version + 1 WHERE id = :v AND version = :seen "
    "RETURNING version"
)


async def update_vendor(ctx: AuthContext, vendor_id: UUID, body: DeliveryVendorPatchIn) -> UUID:
    """A person's edit at the version they saw; fields left out keep their value."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("vendor_1099.update", "role")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_VENDOR, {"v": vendor_id})).first()
    if row is None:
        raise NotFound("vendor")
    engagement_id = await _entity_engagement(ctx, row.client_entity_id, "vendor_1099.update")
    exempt = row.exempt_reason
    if "exempt_reason" in body.model_fields_set:
        exempt = (body.exempt_reason or "").strip() or None
    values = {
        "type": body.entity_type or row.entity_type,
        "attorney": row.is_attorney if body.is_attorney is None else body.is_attorney,
        "exempt": exempt,
        "rents": row.paid_rents if body.paid_rents is None else body.paid_rents,
        "by": ctx.user_id,
        "v": vendor_id,
        "seen": body.expected_version,
    }
    async with uow(ctx.tenant) as tx:
        version = await tx.session.scalar(_EDIT, values)
        if version is None:
            raise StaleVendor(facts={"version": int(row.version)})
        tx.record(
            "vendor.updated",
            target=Target("vendor", vendor_id),
            after=Ref(
                version=int(version), fields=len(body.model_fields_set - {"expected_version"})
            ),
            scope=Scope(engagement_id=engagement_id),
        )
    return vendor_id


SUBSCRIPTIONS: Final = {"ledger_snapshot.recorded": on_ledger_snapshot_recorded}
__all__ = [
    "SUBSCRIPTIONS",
    "StaleVendor",
    "on_ledger_snapshot_recorded",
    "roll_up",
    "rule_texts",
    "tracker",
    "update_vendor",
]
