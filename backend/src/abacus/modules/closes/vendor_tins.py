"""Vendor TIN handling (C-02-T33; TASK-8905; C-02 §4.2, §7; ADR-167 / P-12; DEC-52; red).

- **Sealed at rest.** `record_w9` reads the TIN a person typed from the vendor's W-9 (the W-9 is
  evidence on the vendor's close engagement), seals it under the firm's key bound to the vendor
  (`kernel.crypto.seal`, AAD `vendor_1099_tin:<id>`), and stores the last four, the kind and a
  per-firm fingerprint (one TIN once per client entity). The digits never reach a log, an audit
  event, an outbox event or a payload; `vendors_1099` has no plaintext column (1013).
- **Masked everywhere else.** Every vendor payload carries `tin_last4` only (Restricted,
  `pii_kind=tin`), and `mask_tins_for` nulls it for an offshore reader (AC9.4). The DOM can show
  only what the API sends.
- **Revealed only through P-03.** `reveal_vendor_tin` is evidence's `reveal_field`: a live person
  (never an agent, support session or portal principal), `pii.reveal` on the vendor's close
  engagement (refused offshore, `not_offshore`; fresh MFA), twenty an hour across every reveal,
  and one `pii_reveals` row naming the person (`field_ref vendor:<id>:tin`) plus a `pii.revealed`
  audit event and an access record, before the envelope opens. An offshore or roleless refusal
  answers 403 `tin_reveal_refused`.
- **TIN Matching is a person's record** (`tin_match_results`, source `manual`, with the IRS
  screenshot as evidence): there is no IRS-login automation. A mismatch sets the vendor's W-9
  status to `tin_mismatch`; a later match sets it back to `on_file`.
- **Backup withholding** (`backup_withholding_events`, insert-only): `watch_started`,
  `b_notice_received` (CP2100 with its received date and evidence), `started` at 24% only when a
  B-notice is more than 30 business days old with no new certified TIN since, or no TIN is on
  file (`missing`), and `stopped`. Each event moves the vendor's `backup_withholding` state.

Writes are a person's (the routes refuse anyone else, INV-1), through one unit of work with an
audit event naming fields and codes, never a value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.clock import today
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, ServiceUnavailable
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.closes.business_days import business_days_between
from abacus.modules.closes.compute import information_returns as irc
from abacus.modules.closes.delivery_contract import (
    BackupEvent,
    DeliveryBackupWithholdingIn,
    DeliveryRecordOut,
    DeliveryTinMatchIn,
    DeliveryVendorRowOut,
    DeliveryW9RecordIn,
)
from abacus.modules.closes.delivery_errors import TinRevealRefused
from abacus.modules.engagements.api import EngagementRef, get_ref
from abacus.modules.evidence.api import RevealedField, engagement_of_version, reveal_field
from abacus.modules.identity.api import (
    OFFSHORE_DISCLOSURE,
    AuthContext,
    Forbidden,
    authorise,
    consent_registered,
    is_synthetic_firm,
)
from abacus.modules.organisations.api import (
    TinConflict,
    TinKindNotAllowed,
    fingerprint_tin,
    normalise_tin,
)
from abacus.modules.platform.api import information_return_threshold

BACKUP_RATE: Final = Decimal("24.00")
B_NOTICE_BUSINESS_DAYS: Final = 30
_C19_PURPOSES: Final = ("use", "ai_disclosure", OFFSHORE_DISCLOSURE)
_TIN_UNIQUE: Final = "vendors_1099_one_tin"


class StaleVendor(DomainConflict):
    """The vendor changed since you opened it: reload and try again."""

    code = "stale_version"


class BackupWithholdingNotDue(DomainConflict):
    """Backup withholding starts only 30 business days after a CP2100 B-notice with no new
    certified TIN, or when no TIN is on file (`facts.reason`)."""

    code = "backup_withholding_not_due"


class BackupWithholdingState(DomainConflict):
    """The event does not follow from the vendor's withholding state (`facts.state`)."""

    code = "backup_withholding_state"


class TinNotOnFile(DomainConflict):
    """TIN Matching needs a TIN on file (record the W-9 first)."""

    code = "tin_not_on_file"


class EvidenceRequired(DomainInvalid):
    """This record needs its evidence (the W-9, the TIN Matching screenshot or the notice)."""

    code = "evidence_required"


@dataclass(frozen=True)
class _Vendor:
    id: UUID
    client_entity_id: UUID
    display_name: str
    entity_type: str
    is_attorney: bool
    exempt_reason: str | None
    tin_last4: str | None
    tin_kind: str | None
    w9_status: str
    w9_signed_on: date | None
    backup_withholding: str
    version: int
    engagement: EngagementRef


_VENDOR = text(
    "SELECT id, client_entity_id, display_name, entity_type, is_attorney, exempt_reason, "
    "tin_last4, tin_kind, w9_status, w9_signed_on, backup_withholding, version "
    "FROM vendors_1099 WHERE id = :id"
)
# The vendor's close engagement: the client entity's latest close (vendors are read from the
# entity's ledger, which the CAS engagement closes).
_ENGAGEMENT = text(
    "SELECT engagement_id FROM closes WHERE client_entity_id = :e ORDER BY period DESC LIMIT 1"
)


async def _vendor(ctx: AuthContext, vendor_id: UUID, action: str) -> _Vendor:
    """The vendor after `action` is authorised on its close engagement. Unknown, walled or on an
    entity with no close: 404 (INV-3), before anything is read beyond the row."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_VENDOR, {"id": vendor_id})).one_or_none()
        engagement_id = (
            None if row is None else await session.scalar(_ENGAGEMENT, {"e": row.client_entity_id})
        )
    if row is None or engagement_id is None:
        raise NotFound("vendor")
    try:
        engagement = await get_ref(ctx, cast(UUID, engagement_id))
        await authorise(ctx, action, engagement.resource())
    except NotFound:
        raise NotFound("vendor") from None
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("vendor") from None
        raise
    return _Vendor(
        row.id, row.client_entity_id, row.display_name, row.entity_type, row.is_attorney,
        row.exempt_reason, row.tin_last4, row.tin_kind, row.w9_status, row.w9_signed_on,
        row.backup_withholding, row.version, engagement,
    )  # fmt: skip


async def _evidence_on(ctx: AuthContext, vendor: _Vendor, version_id: UUID | None) -> UUID:
    """The evidence version, when it sits on the vendor's close engagement (else 404)."""
    if version_id is None:
        raise EvidenceRequired
    if await engagement_of_version(ctx.tenant, version_id) != vendor.engagement.id:
        raise NotFound("evidence_version")
    return version_id


def _aad(vendor_id: UUID) -> str:
    """The envelope opens only as this vendor's TIN: a sealed value copied elsewhere won't."""
    return f"vendor_1099_tin:{vendor_id}"


# --- read ----------------------------------------------------------------------------------------

_ROLLUPS = text(
    "SELECT tax_year, method, amount, txn_count FROM vendor_payment_rollups "
    "WHERE vendor_id = :v AND tax_year = (SELECT max(tax_year) FROM vendor_payment_rollups "
    "WHERE vendor_id = :v)"
)


async def get_vendor(ctx: AuthContext, vendor_id: UUID) -> DeliveryVendorRowOut:
    """CLS-13's vendor drawer: the latest tax year's rolled-up payments and what they make the
    vendor (code, ADR-050), with the TIN's last four only."""
    vendor = await _vendor(ctx, vendor_id, "information_returns.read")
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ROLLUPS, {"v": vendor_id})).all()
    payments = [irc.Payment(r.method, Decimal(r.amount), int(r.txn_count)) for r in rows]
    year = rows[0].tax_year if rows else None
    threshold = await _threshold(year) if year is not None else None
    found = irc.classify(
        irc.VendorFacts(vendor.entity_type, vendor.is_attorney, vendor.exempt_reason),
        payments,
        threshold,
    )
    return _row_out(vendor, found)


async def _threshold(year: int) -> irc.Threshold:
    """C21's 1099-NEC threshold for the payment year (K-02's reference set). None published:
    503, never a default (DEC-85)."""
    try:
        found = await information_return_threshold("nec", year)
    except LookupError:
        raise ServiceUnavailable("information_return_thresholds") from None
    return irc.Threshold(Decimal(found.threshold_usd), found.min_transactions)


def _row_out(vendor: _Vendor, found: irc.Classification) -> DeliveryVendorRowOut:
    return DeliveryVendorRowOut(
        vendor_id=vendor.id,
        display_name=vendor.display_name,
        entity_type=cast(irc.EntityType, vendor.entity_type),
        is_attorney=vendor.is_attorney,
        reportability=found.reportability,
        form=found.form,
        box=found.box,
        amount=found.amount,
        tin_last4=vendor.tin_last4,
        w9_status=cast(irc.W9Status, vendor.w9_status),
        version=vendor.version,
    )


# --- the W-9's TIN -------------------------------------------------------------------------------

_WRITE_TIN = text(
    "UPDATE vendors_1099 SET tin_sealed = :sealed, tin_last4 = :last4, tin_kind = :kind, "
    "tin_fingerprint = :fingerprint, w9_status = 'on_file', w9_evidence_version_id = :evidence, "
    "w9_signed_on = :signed, updated_by = :by, updated_at = abacus_now(), "
    "version = version + 1 WHERE id = :id AND version = :seen RETURNING version"
)


async def record_w9(
    ctx: AuthContext, vendor_id: UUID, body: DeliveryW9RecordIn
) -> DeliveryVendorRowOut:
    """A person records the vendor's W-9: the TIN is sealed and the W-9 is on file. 422
    `tin_invalid`, 422 `tin_kind_not_allowed` (an SSN before C19's gate, real firms), 409
    `tin_conflict` (that TIN is on another vendor of the entity), 409 `stale_version`."""
    vendor = await _vendor(ctx, vendor_id, "vendor_1099.update")
    evidence = await _evidence_on(ctx, vendor, body.evidence_version_id)
    digits = normalise_tin(body.tin.get_secret_value())
    if body.tin_kind == "ssn" and not (
        all(consent_registered(p) for p in _C19_PURPOSES) or await is_synthetic_firm(ctx.tenant)
    ):
        raise TinKindNotAllowed(facts={"vendor_id": str(vendor_id)})
    sealed = await seal(ctx.tenant_id, digits.encode(), _aad(vendor_id))
    async with uow(ctx.tenant) as tx:
        try:
            async with tx.session.begin_nested():
                version = await tx.session.scalar(
                    _WRITE_TIN,
                    {
                        "sealed": sealed,
                        "last4": digits[-4:],
                        "kind": body.tin_kind,
                        "fingerprint": fingerprint_tin(ctx.tenant_id, digits),
                        "evidence": evidence,
                        "signed": body.signed_on,
                        "by": ctx.user_id,
                        "id": vendor_id,
                        "seen": body.expected_version,
                    },
                )
        except IntegrityError as exc:
            if _TIN_UNIQUE in str(exc.orig):
                raise TinConflict from None
            raise
        if version is None:
            raise StaleVendor(facts={"version": vendor.version})
        tx.record(
            "vendor.updated",
            target=Target("vendor", vendor_id),
            after=Ref(tin=1, evidence_version_id=evidence),
            scope=Scope(engagement_id=vendor.engagement.id),
        )
    return await get_vendor(ctx, vendor_id)


# --- the reveal ----------------------------------------------------------------------------------

_SEALED = text("SELECT tin_sealed, tin_kind FROM vendors_1099 WHERE id = :id")


async def reveal_vendor_tin(ctx: AuthContext, vendor_id: UUID) -> tuple[str, RevealedField]:
    """The one call that returns a vendor's TIN in the clear (P-03's `reveal_field`). 404 for an
    unknown or walled vendor, or no TIN on file; 403 `tin_reveal_refused` offshore or without the
    role; 403 `mfa_required` when only MFA is stale; 429 past twenty reveals an hour."""
    vendor = await _vendor(ctx, vendor_id, "information_returns.read")
    if vendor.tin_kind is None:
        raise NotFound("tin")
    kind = vendor.tin_kind

    async def opened() -> str:
        async with tenant_session(ctx.tenant) as session:
            found = (await session.execute(_SEALED, {"id": vendor_id})).one_or_none()
        if found is None or found.tin_sealed is None:
            raise NotFound("tin")
        plain = await open_sealed(ctx.tenant_id, bytes(found.tin_sealed), _aad(vendor_id))
        return plain.decode()

    try:
        revealed = await reveal_field(
            ctx,
            vendor.engagement.id,
            f"vendor:{vendor_id}:tin",
            kind,
            opened,
            context_ref="closes.information_returns",
        )
    except Forbidden as refused:
        if refused.layer == "attribute":
            raise  # MFA: the shell steps up and retries
        raise TinRevealRefused(facts={"vendor_id": str(vendor_id)}) from None
    return kind, revealed


# --- TIN Matching --------------------------------------------------------------------------------

_MATCH = text(
    "INSERT INTO tin_match_results (tenant_id, vendor_id, checked_on, result, recorded_by, "
    "evidence_version_id) VALUES (:t, :v, :on, :result, :by, :evidence) RETURNING id"
)
_W9_STATUS = text(
    "UPDATE vendors_1099 SET w9_status = :status, updated_by = :by, updated_at = abacus_now(), "
    "version = version + 1 WHERE id = :id"
)


async def record_tin_match(
    ctx: AuthContext, vendor_id: UUID, body: DeliveryTinMatchIn
) -> DeliveryRecordOut:
    """A person's IRS TIN Matching result with its evidence. A mismatch, `not_issued` or
    `invalid` makes the W-9 status `tin_mismatch`; a match after a mismatch sets it back."""
    vendor = await _vendor(ctx, vendor_id, "tin_match.record")
    if vendor.tin_kind is None:
        raise TinNotOnFile(facts={"vendor_id": str(vendor_id)})
    evidence = await _evidence_on(ctx, vendor, body.evidence_version_id)
    status = irc.w9_status_after_match(vendor.w9_status, body.result)
    async with uow(ctx.tenant) as tx:
        record_id = await tx.session.scalar(
            _MATCH,
            {
                "t": ctx.tenant_id,
                "v": vendor_id,
                "on": body.checked_on,
                "result": body.result,
                "by": ctx.user_id,
                "evidence": evidence,
            },
        )
        if status != vendor.w9_status:
            await tx.session.execute(
                _W9_STATUS, {"status": status, "by": ctx.user_id, "id": vendor_id}
            )
        tx.record(
            "tin_match.recorded",
            target=Target("vendor", vendor_id),
            after=Ref(record_id=cast(UUID, record_id), evidence_version_id=evidence),
            scope=Scope(engagement_id=vendor.engagement.id),
        )
    return DeliveryRecordOut(record_id=cast(UUID, record_id))


# --- backup withholding --------------------------------------------------------------------------

_LAST_NOTICE = text(
    "SELECT notice_received_on FROM backup_withholding_events WHERE vendor_id = :v "
    "AND event = 'b_notice_received' ORDER BY at DESC LIMIT 1"
)
_EVENT = text(
    "INSERT INTO backup_withholding_events (tenant_id, vendor_id, event, reason, rate_percent, "
    "notice_received_on, recorded_by, evidence_version_id) VALUES (:t, :v, :event, :reason, "
    ":rate, :notice, :by, :evidence) RETURNING id"
)
_BACKUP_STATE = text(
    "UPDATE vendors_1099 SET backup_withholding = :state, updated_by = :by, "
    "updated_at = abacus_now(), version = version + 1 WHERE id = :id"
)


async def record_backup_withholding(
    ctx: AuthContext, vendor_id: UUID, body: DeliveryBackupWithholdingIn
) -> DeliveryRecordOut:
    """A person's backup-withholding event, with its reason. `b_notice_received` needs the notice
    (evidence) and its received date; `started` is 24% and only when due (30 business days after
    the latest B-notice with no TIN certified since, or no TIN on file: 409
    `backup_withholding_not_due` otherwise)."""
    vendor = await _vendor(ctx, vendor_id, "backup_withholding.record")
    event: BackupEvent = body.event
    state = irc.backup_state_after(vendor.backup_withholding, event)
    if state is None:
        raise BackupWithholdingState(facts={"state": vendor.backup_withholding, "event": event})
    evidence: UUID | None = None
    if body.evidence_version_id is not None or event == "b_notice_received":
        evidence = await _evidence_on(ctx, vendor, body.evidence_version_id)
    notice_on: date | None = None
    if event == "b_notice_received":
        if body.notice_received_on is None:
            raise EvidenceRequired(facts={"field": "notice_received_on"})
        notice_on = body.notice_received_on
    rate: Decimal | None = None
    if event == "started":
        await _withholding_due(ctx, vendor)
        rate = BACKUP_RATE
    async with uow(ctx.tenant) as tx:
        record_id = await tx.session.scalar(
            _EVENT,
            {
                "t": ctx.tenant_id,
                "v": vendor_id,
                "event": event,
                "reason": body.reason,
                "rate": rate,
                "notice": notice_on,
                "by": ctx.user_id,
                "evidence": evidence,
            },
        )
        if state != vendor.backup_withholding:
            await tx.session.execute(
                _BACKUP_STATE, {"state": state, "by": ctx.user_id, "id": vendor_id}
            )
        tx.record(
            "backup_withholding.recorded",
            target=Target("vendor", vendor_id),
            after=Ref(record_id=cast(UUID, record_id)),
            scope=Scope(engagement_id=vendor.engagement.id),
        )
    return DeliveryRecordOut(record_id=cast(UUID, record_id))


async def _withholding_due(ctx: AuthContext, vendor: _Vendor) -> None:
    if vendor.w9_status == "missing" or vendor.tin_kind is None:
        return  # no TIN on file: withholding is due now
    async with tenant_session(ctx.tenant) as session:
        notice: date | None = await session.scalar(_LAST_NOTICE, {"v": vendor.id})
    if notice is None:
        raise BackupWithholdingNotDue(facts={"reason": "no_b_notice"})
    if vendor.w9_signed_on is not None and vendor.w9_signed_on > notice:
        raise BackupWithholdingNotDue(facts={"reason": "tin_certified_since_notice"})
    elapsed = await business_days_between(notice, await today())
    if elapsed <= B_NOTICE_BUSINESS_DAYS:
        raise BackupWithholdingNotDue(
            facts={"reason": "within_30_business_days", "business_days": elapsed}
        )


__all__ = [
    "BACKUP_RATE",
    "B_NOTICE_BUSINESS_DAYS",
    "BackupWithholdingNotDue",
    "BackupWithholdingState",
    "EvidenceRequired",
    "StaleVendor",
    "TinNotOnFile",
    "get_vendor",
    "record_backup_withholding",
    "record_tin_match",
    "record_w9",
    "reveal_vendor_tin",
]
