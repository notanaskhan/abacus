"""Information returns, pure (C-02-T33; TASK-8905; C-02 §4.2; CLS-13; ADR-050).

Code computes; nothing here reads a database, the clock or a model.

- `classify`: what a vendor's rolled-up payments make it for the year. Card and payment-app
  payments are the processor's to report (Form 1099-K), so they never count; a corporation (C, S
  or an LLC taxed as one) is exempt unless it is an attorney; a recorded exemption reason exempts;
  below the year's threshold is `below_threshold`; otherwise `reportable` on 1099-NEC box 1
  (fees, attorneys' fees included). The 1099-MISC boxes (rents, gross proceeds to an attorney)
  need the payment's ledger category, which CLS-13's tracker reads (C-02-T45).
- `w9_status_after_match`: a TIN Matching result's effect on the W-9 status.
- `backup_state_after`: the backup-withholding state an event leads to, or None when the event
  does not follow (a second `started`, a `stopped` with nothing running).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, cast

EntityType = Literal[
    "individual", "single_member_llc", "partnership", "c_corporation", "s_corporation",
    "trust_estate", "llc_c", "llc_s", "llc_p", "other", "unknown",
]  # fmt: skip
W9Status = Literal["on_file", "requested", "tin_mismatch", "missing"]
Reportability = Literal["reportable", "below_threshold", "exempt_corporation", "paid_by_card"]
Form = Literal["nec", "misc"]
MatchResult = Literal["match", "mismatch", "not_issued", "invalid"]
BackupState = Literal["none", "watch", "started"]
BackupEvent = Literal["watch_started", "b_notice_received", "started", "stopped"]

PROCESSOR_METHODS: Final = frozenset({"card", "payment_app"})
CORPORATIONS: Final = frozenset({"c_corporation", "s_corporation", "llc_c", "llc_s"})
ZERO: Final = Decimal("0.00")


@dataclass(frozen=True)
class Payment:
    method: str
    amount: Decimal
    txn_count: int


@dataclass(frozen=True)
class VendorFacts:
    entity_type: str
    is_attorney: bool
    exempt_reason: str | None


@dataclass(frozen=True)
class Threshold:
    threshold_usd: Decimal
    min_transactions: int | None


@dataclass(frozen=True)
class Classification:
    reportability: Reportability
    amount: Decimal  # the payments that count (processor payments excluded)
    form: Form | None
    box: str | None


def classify(
    vendor: VendorFacts, payments: list[Payment], threshold: Threshold | None
) -> Classification:
    """The vendor's reportability for one tax year. `threshold` None means no payments (nothing
    to compare); with payments the caller must supply the year's threshold."""
    counted = [p for p in payments if p.method not in PROCESSOR_METHODS]
    amount = sum((p.amount for p in counted), ZERO).quantize(Decimal("0.01"))
    if payments and not counted:
        return Classification("paid_by_card", ZERO, None, None)
    if vendor.exempt_reason is not None or (
        vendor.entity_type in CORPORATIONS and not vendor.is_attorney
    ):
        return Classification("exempt_corporation", amount, None, None)
    if threshold is None or amount < threshold.threshold_usd:
        return Classification("below_threshold", amount, None, None)
    return Classification("reportable", amount, "nec", "1")


def w9_status_after_match(current: str, result: MatchResult) -> W9Status:
    """A mismatch, a TIN not issued or an invalid TIN puts the W-9 in `tin_mismatch`; a match
    clears a mismatch (`on_file`) and leaves any other status as it is."""
    if result != "match":
        return "tin_mismatch"
    if current == "tin_mismatch":
        return "on_file"
    return cast(W9Status, current)


_BACKUP: Final[dict[tuple[str, str], BackupState]] = {
    ("none", "watch_started"): "watch",
    ("none", "b_notice_received"): "watch",
    ("watch", "b_notice_received"): "watch",
    ("none", "started"): "started",
    ("watch", "started"): "started",
    ("watch", "stopped"): "none",
    ("started", "stopped"): "none",
    ("started", "b_notice_received"): "started",
}


def backup_state_after(current: str, event: BackupEvent) -> BackupState | None:
    return _BACKUP.get((current, event))


__all__ = [
    "CORPORATIONS",
    "PROCESSOR_METHODS",
    "BackupEvent",
    "BackupState",
    "Classification",
    "EntityType",
    "Form",
    "MatchResult",
    "Payment",
    "Reportability",
    "Threshold",
    "VendorFacts",
    "W9Status",
    "backup_state_after",
    "classify",
    "w9_status_after_match",
]
