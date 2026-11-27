"""W-9 requests and the 1099 filing record (C-02-T46; TASK-9004; C-02 F9 US-9.2, US-9.4; CLS-13
b, d, d2, e; ADR P-18 / DEC-49 never transmit; DEC-6010; amber).

- **W-9 requests** (`request_w9s`, `POST …/w9-requests`, `w9.request`): a person asks the client
  through the portal for each vendor's W-9: one request item per vendor on the entity's close
  engagement, created and **sent by that person in one unit of work** through `requests.api`
  (its scope check and Undo window), so the client sees them on POR-11. The firm's wording template
  version is pinned on the `w9_requests` row. Each vendor reads `requested`. The vendor link
  channel stays unavailable until R-03 (the table refuses it).
- **Batch approval** (`approve_batch`, `POST /v1/information-return-batches`): a manager or
  partner, a live person, only after the year's December close is locked (409
  `close_not_locked`), at the vendor versions they saw (409 `stale_version`). One
  `information_returns` row per reportable vendor (code's classification, ADR-050) with the C21
  threshold version it was judged under; the due date is C21's (503 when no rule is published).
- **IRIS file** (`iris_csv`): a deterministic CSV (fixed columns, the batch's order, `\\n` line
  ends) for the firm to upload in the IRS IRIS Taxpayer Portal under its own credentials
  [verify the IRIS template]. It needs each recipient's TIN, opened from the sealed store for the
  file only (never logged, never in an event); a vendor without a W-9 TIN refuses the export (409
  `tin_missing`). The file's SHA-256 is recorded; Accrued never transmits (no IRS host anywhere).
- **Filed and acknowledged** (`record_filing`, `record_ack`): a person records "Filed · IRIS" with
  the receipt id and the confirmation as evidence, then the IRS's acceptance or rejection with its
  evidence.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import TextClause, text

from abacus.kernel import clock
from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound, ServiceUnavailable
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.closes.compute import information_returns as irc
from abacus.modules.closes.delivery_contract import (
    BatchStatus,
    DeliveryAckIn,
    DeliveryFiledIn,
    DeliveryReturnBatchIn,
    DeliveryReturnBatchOut,
    DeliveryW9RequestIn,
    DeliveryW9RequestOut,
)
from abacus.modules.identity.api import AuthContext, Forbidden

TARGET: Final = "information_return_batch"
IRIS_COLUMNS: Final = (
    "Form Type", "Tax Year", "Recipient TIN Type", "Recipient TIN", "Recipient Name",
    "Box", "Amount",
)  # fmt: skip
_FORM_NAMES: Final = {"nec": "1099-NEC", "misc": "1099-MISC"}


class CloseNotLocked(DomainConflict):
    code = "close_not_locked"
    message = "Opens after the December close locks."


class StaleVendors(DomainConflict):
    code = "stale_version"


class BatchExists(DomainConflict):
    code = "batch_exists"


class TinMissing(DomainConflict):
    code = "tin_missing"


class WrongStatus(DomainConflict):
    code = "transition_not_available"


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _engagement(ctx: AuthContext, client_entity_id: UUID, action: str) -> UUID:
    from abacus.modules.closes.vendor_rollups import (
        _entity_engagement,  # pyright: ignore[reportPrivateUsage] -- the sibling's one authorisation
    )

    return await _entity_engagement(ctx, client_entity_id, action)


# --- W-9 requests --------------------------------------------------------------------------------

_VENDORS_OF: Final = text(
    "SELECT id, display_name, w9_status FROM vendors_1099 WHERE client_entity_id = :e "
    "AND id = ANY(:ids) ORDER BY display_name, id"
)
_W9_ROW: Final = text(
    "INSERT INTO w9_requests (id, tenant_id, client_entity_id, vendor_ids, channel, "
    "request_item_ids, wording_template_version_id, sent_by) VALUES (:id, :t, :e, :v, 'portal', "
    ":items, :tpl, :by)"
)
_REQUESTED: Final = text(
    "UPDATE vendors_1099 SET w9_status = 'requested', updated_by = :by, "
    "updated_at = abacus_now(), version = version + 1 WHERE id = ANY(:ids) "
    "AND w9_status IN ('missing', 'requested')"
)


async def request_w9s(
    ctx: AuthContext, client_entity_id: UUID, body: DeliveryW9RequestIn
) -> DeliveryW9RequestOut:
    from abacus.modules.requests.api import BulkItem, create_items_bulk, send_created

    _human(ctx, "w9.request")
    engagement_id = await _engagement(ctx, client_entity_id, "w9.request")
    async with tenant_session(ctx.tenant) as session:
        vendors = list(
            await session.execute(
                _VENDORS_OF, {"e": client_entity_id, "ids": list(dict.fromkeys(body.vendor_ids))}
            )
        )
    if len(vendors) != len(set(body.vendor_ids)):
        raise NotFound("vendor")
    request_id = uuid4()
    async with uow(ctx.tenant) as tx:
        items = await create_items_bulk(
            tx,
            ctx,
            engagement_id,
            [
                BulkItem(
                    description=f"Form W-9: {v.display_name}"[:500],
                    audit_area="1099",
                    linked_ref={"type": "w9_request", "vendor_id": str(v.id)},
                )
                for v in vendors
            ],
            wave="year_end",  # the 1099 season: request_items waves are planning, year_end, sample
            due_on=None,
            batch_id=request_id,
        )
        for item in items:
            await send_created(tx, ctx, engagement_id, item)  # the person's own send
        await tx.session.execute(
            _W9_ROW,
            {"id": request_id, "t": ctx.tenant_id, "e": client_entity_id,
             "v": [v.id for v in vendors], "items": items,
             "tpl": body.wording_template_version_id, "by": ctx.user_id},
        )  # fmt: skip
        await tx.session.execute(_REQUESTED, {"ids": [v.id for v in vendors], "by": ctx.user_id})
        tx.record(
            "vendor_document.requested",  # a W-9, through the portal
            # audit target types are letters and underscores: the `w9_requests` row
            target=Target("vendor_document_request", request_id),
            after=Ref(vendors=len(vendors), channel_portal=1),
            scope=Scope(engagement_id=engagement_id),
        )
    return DeliveryW9RequestOut(request_id=request_id, request_item_ids=items)


# --- the batch -----------------------------------------------------------------------------------

_DECEMBER: Final = text("SELECT status FROM closes WHERE client_entity_id = :e AND period = :p")
_CANDIDATES: Final = text(
    "SELECT v.id, v.entity_type, v.is_attorney, v.exempt_reason, v.paid_rents, v.version, "
    "r.method, r.amount, r.txn_count FROM vendors_1099 v JOIN vendor_payment_rollups r "
    "ON r.vendor_id = v.id WHERE v.client_entity_id = :e AND r.tax_year = :y "
    "ORDER BY v.display_name, v.id, r.method"
)
_NEW_BATCH: Final = text(
    "INSERT INTO information_return_batches (id, tenant_id, client_entity_id, tax_year, due_on) "
    "VALUES (:id, :t, :e, :y, :due) ON CONFLICT (tenant_id, client_entity_id, tax_year) "
    "DO NOTHING RETURNING id"
)
_APPROVE: Final = text(
    "UPDATE information_return_batches SET status = 'approved', approved_by = :by, "
    "approved_at = :at, version = version + 1 WHERE id = :b AND status = 'not_started'"
)
_RETURN: Final = text(
    "INSERT INTO information_returns (tenant_id, batch_id, vendor_id, form, box, amount, "
    "threshold_ref) VALUES (:t, :b, :v, :form, :box, :amount, :ref)"
)
_BATCH: Final = text(
    "SELECT id, client_entity_id, tax_year, status, due_on, version FROM "
    "information_return_batches WHERE id = :b"
)
_COUNT: Final = text("SELECT count(*) FROM information_returns WHERE batch_id = :b")


async def _view(ctx: AuthContext, batch_id: UUID) -> DeliveryReturnBatchOut:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_BATCH, {"b": batch_id})).first()
        forms = int(await session.scalar(_COUNT, {"b": batch_id}) or 0)
    if row is None:
        raise NotFound(TARGET)
    return DeliveryReturnBatchOut(
        batch_id=row.id, status=cast(BatchStatus, row.status), forms=forms, due_on=row.due_on
    )


async def _due_on(tax_year: int) -> date:
    from abacus.modules.tax.api import due_dates_for

    try:
        return (await due_dates_for("1099-NEC", tax_year, date(tax_year, 12, 31))).original_due_on
    except LookupError:
        raise ServiceUnavailable("information_return_due_dates") from None


async def approve_batch(ctx: AuthContext, body: DeliveryReturnBatchIn) -> DeliveryReturnBatchOut:
    from abacus.modules.closes.vendor_rollups import rule_texts
    from abacus.modules.platform.api import information_return_threshold

    _human(ctx, "information_return_batch.approve")
    engagement_id = await _engagement(
        ctx, body.client_entity_id, "information_return_batch.approve"
    )
    async with tenant_session(ctx.tenant) as session:
        december = await session.scalar(
            _DECEMBER, {"e": body.client_entity_id, "p": f"{body.tax_year}-12"}
        )
        lines = list(
            await session.execute(_CANDIDATES, {"e": body.client_entity_id, "y": body.tax_year})
        )
    if december != "locked":
        raise CloseNotLocked(facts={"period": f"{body.tax_year}-12"})
    threshold, _, _ = await rule_texts(body.tax_year)
    threshold_ref = str(
        (await information_return_threshold("nec", body.tax_year)).reference_set_version_id
    )
    facts: dict[UUID, tuple[irc.VendorFacts, int]] = {}
    payments: dict[UUID, list[irc.Payment]] = {}
    for r in lines:
        facts[r.id] = (
            irc.VendorFacts(r.entity_type, r.is_attorney, r.exempt_reason, r.paid_rents),
            int(r.version),
        )
        if Decimal(r.amount) > 0:
            payments.setdefault(r.id, []).append(
                irc.Payment(str(r.method), Decimal(r.amount), int(r.txn_count))
            )
    stale = [str(v) for v, (_, version) in facts.items() if body.seen_versions.get(v) != version]
    if stale:
        raise StaleVendors(facts={"vendors": len(stale)})
    forms = [
        (vendor, found)
        for vendor, paid in payments.items()
        if (found := irc.classify(facts[vendor][0], paid, threshold)).reportability == "reportable"
    ]
    due_on = await _due_on(body.tax_year)
    batch_id = uuid4()
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        made = await tx.session.scalar(
            _NEW_BATCH,
            {"id": batch_id, "t": ctx.tenant_id, "e": body.client_entity_id,
             "y": body.tax_year, "due": due_on},
        )  # fmt: skip
        if made is None:
            raise BatchExists(facts={"tax_year": body.tax_year})
        await tx.session.execute(_APPROVE, {"b": batch_id, "by": ctx.user_id, "at": now})
        for vendor, found in forms:
            await tx.session.execute(
                _RETURN,
                {"t": ctx.tenant_id, "b": batch_id, "v": vendor, "form": found.form,
                 "box": found.box, "amount": found.amount, "ref": threshold_ref},
            )  # fmt: skip
        tx.record(
            "information_return_batch.approved",
            target=Target(TARGET, batch_id),
            after=Ref(forms=len(forms), tax_year=body.tax_year),
            scope=Scope(engagement_id=engagement_id),
        )
    return await _view(ctx, batch_id)


# --- the IRIS file and the filing record ---------------------------------------------------------

_FILE_ROWS: Final = text(
    "SELECT r.vendor_id, r.form, r.box, r.amount, v.display_name, v.tin_kind, v.tin_sealed "
    "FROM information_returns r JOIN vendors_1099 v ON v.id = r.vendor_id "
    "WHERE r.batch_id = :b ORDER BY r.form, v.display_name, r.vendor_id"
)
_EXPORTED: Final = text(
    "UPDATE information_return_batches SET status = 'exported', exported_by = :by, "
    "exported_at = :at, iris_file_sha256 = :sha, version = version + 1 WHERE id = :b "
    "AND status IN ('approved', 'exported')"
)


@dataclass(frozen=True)
class IrisFile:
    content: bytes
    sha256: str


def iris_rows(tax_year: int, rows: list[tuple[str, str, str, str, str, Decimal]]) -> bytes:
    """Deterministic: fixed columns, the given order, `\\n` line ends. Each row is (form, box,
    tin kind, tin, name, amount). The recipient's name is client-system text: a leading formula
    character is neutralised (ADR-052)."""
    from abacus.kernel.safe_xlsx import safe_text

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(IRIS_COLUMNS)
    for form, box, kind, tin, name, amount in rows:
        writer.writerow(
            [_FORM_NAMES[form], tax_year, kind.upper(), tin, safe_text(name), box, f"{amount:.2f}"]
        )
    return out.getvalue().encode()


async def iris_csv(ctx: AuthContext, batch_id: UUID) -> IrisFile:
    _human(ctx, "information_return_batch.export")
    async with tenant_session(ctx.tenant) as session:
        batch = (await session.execute(_BATCH, {"b": batch_id})).first()
        rows = list(await session.execute(_FILE_ROWS, {"b": batch_id})) if batch else []
    if batch is None:
        raise NotFound(TARGET)
    engagement_id = await _engagement(
        ctx, batch.client_entity_id, "information_return_batch.export"
    )
    if batch.status not in ("approved", "exported"):
        raise WrongStatus(facts={"status": str(batch.status)})
    if any(r.tin_sealed is None for r in rows):
        raise TinMissing(facts={"vendors": sum(1 for r in rows if r.tin_sealed is None)})
    lines = [
        (
            str(r.form), str(r.box), str(r.tin_kind),
            (await open_sealed(ctx.tenant_id, bytes(r.tin_sealed),
                               f"vendor_1099_tin:{r.vendor_id}")).decode(),
            str(r.display_name), Decimal(r.amount),
        )
        for r in rows
    ]  # fmt: skip
    content = iris_rows(int(batch.tax_year), lines)
    sha = hashlib.sha256(content).hexdigest()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _EXPORTED, {"b": batch_id, "by": ctx.user_id, "at": await clock.now(ctx.tenant),
                        "sha": sha},
        )  # fmt: skip
        tx.record(
            "information_return_batch.exported",
            target=Target(TARGET, batch_id),
            after=Ref(forms=len(lines)),
            scope=Scope(engagement_id=engagement_id),
        )
    return IrisFile(content, sha)


_FILED: Final = text(
    "UPDATE information_return_batches SET status = 'filed_iris', iris_receipt_id = :receipt, "
    "filed_on = :on, filed_at = :at, filed_recorded_by = :by, filed_evidence_version_id = :ev, "
    "version = version + 1 WHERE id = :b AND status = 'exported' RETURNING id"
)
_ACK: Final = text(
    "UPDATE information_return_batches SET status = :s, ack_at = :at, ack_recorded_by = :by, "
    "ack_evidence_version_id = :ev, version = version + 1 WHERE id = :b "
    "AND status = 'filed_iris' RETURNING id"
)


async def _evidence_on(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> UUID:
    from abacus.modules.evidence.api import engagement_of_version

    if await engagement_of_version(ctx.tenant, version_id) != engagement_id:
        raise NotFound("evidence_version")
    return version_id


async def _transition(
    ctx: AuthContext, batch_id: UUID, action: str, sql: TextClause, values: dict[str, object],
    evidence_id: UUID, event: str,
) -> DeliveryReturnBatchOut:  # fmt: skip
    _human(ctx, action)
    async with tenant_session(ctx.tenant) as session:
        batch = (await session.execute(_BATCH, {"b": batch_id})).first()
    if batch is None:
        raise NotFound(TARGET)
    engagement_id = await _engagement(ctx, batch.client_entity_id, action)
    evidence = await _evidence_on(ctx, engagement_id, evidence_id)
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.scalar(
            sql, {**values, "b": batch_id, "by": ctx.user_id, "ev": evidence}
        )
        if moved is None:
            raise WrongStatus(facts={"status": str(batch.status)})
        tx.record(event, target=Target(TARGET, batch_id), scope=Scope(engagement_id=engagement_id))
    return await _view(ctx, batch_id)


async def record_filing(
    ctx: AuthContext, batch_id: UUID, body: DeliveryFiledIn
) -> DeliveryReturnBatchOut:
    return await _transition(
        ctx, batch_id, "information_return_batch.record_filing", _FILED,
        {"receipt": body.iris_receipt_id, "on": body.filed_on,
         "at": await clock.now(ctx.tenant)},
        body.evidence_version_id, "information_return_batch.filed",
    )  # fmt: skip


async def record_ack(
    ctx: AuthContext, batch_id: UUID, body: DeliveryAckIn
) -> DeliveryReturnBatchOut:
    at: datetime = body.at
    return await _transition(
        ctx, batch_id, "information_return_batch.record_ack", _ACK,
        {"s": body.status, "at": at}, body.evidence_version_id,
        f"information_return_batch.{body.status}",
    )  # fmt: skip


__all__ = [
    "IRIS_COLUMNS",
    "BatchExists",
    "CloseNotLocked",
    "IrisFile",
    "StaleVendors",
    "TinMissing",
    "approve_batch",
    "iris_csv",
    "iris_rows",
    "record_ack",
    "record_filing",
    "request_w9s",
]
