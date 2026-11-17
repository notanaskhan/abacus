"""The C12 TB hand-off slice (T-06-T05; TASK-8514; T-06 §5.3; SPEC-702 F6): Granite Peak Outdoor
Supply, Inc.'s released FY2026 Final TB handed to its FY2026 Form 1120 (AUD-38 a-e, TXP-13 d), and
Copperleaf's locked December 2026 close handed to its 2026 Form 1120-S through `close_lock`
(C-02's CLS-12). Every figure is the AUD-38 and CLS-12 handoffs'; typed by the C12 models so a
contract change fails here. No database code: the landing loads through the services (T-06-T20,
T39)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Final

from abacus.modules.tax.api import tb_handoff_contract as _contract
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT

TbHandoffBookIncomeOut = _contract.TbHandoffBookIncomeOut
TbHandoffCountsOut = _contract.TbHandoffCountsOut
TbHandoffLandingOut = _contract.TbHandoffLandingOut
TbHandoffPreviewOut = _contract.TbHandoffPreviewOut
TbHandoffReviewAccountOut = _contract.TbHandoffReviewAccountOut
TbHandoffTaxItemOut = _contract.TbHandoffTaxItemOut

D = Decimal
GRANITE_PEAK: Final = "Granite Peak Outdoor Supply, Inc."
TARGET_RETURN: Final = "FY2026 Form 1120"
RELEASED_ON: Final = datetime(2026, 10, 27, tzinfo=CT)  # Margaret Okonkwo
HANDED_OFF_AT: Final = datetime(2026, 11, 9, 10, 30, tzinfo=CT)  # Hannah Leclerc
TAX_TEAM: Final = ("Leo Wong", "Isaac Moreau", "Victor Hammond")
_NS: Final = uuid.UUID("5f0c12a0-0000-4000-8000-000000000c12")


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


REVIEW_ACCOUNTS: Final = (
    ("2255", "Accrued customer loyalty rewards", D("-84600.00")),
    ("6875", "Small equipment expensed", D("41200.00")),
)
PPE: Final = (
    D("6050000.00"),
    D("1380000.00"),
    D("1050000.00"),
)  # opening + additions - depreciation
ACCRUED_LIABILITIES: Final = D("1630000.00")
PASSED_AJE_3: Final = D("68400.00")


def granite_peak_preview(*, chosen: bool) -> TbHandoffPreviewOut:
    """AUD-38 b (`chosen=False`, 10:12 AM) or a (`chosen=True`, both Send blank, 10:29 AM)."""
    reviews = [
        TbHandoffReviewAccountOut(
            account_ref=ref,
            account_name=name,
            balance=balance,
            choice="send_blank" if chosen else None,
            source="tb_mapper",
        )
        for ref, name, balance in REVIEW_ACCOUNTS
    ]
    return TbHandoffPreviewOut(
        source_kind="audit_release",
        source_snapshot_id=_id("granite-peak-final-tb-fy2026"),
        gate="released",
        status="ready" if chosen else "needs_review",
        counts=TbHandoffCountsOut(mapped=121, suggested=5, review=2, total=128),
        review_accounts=reviews,
        book_income=TbHandoffBookIncomeOut(
            pretax=D("3100000.00"), income_tax_expense=D("750000.00"), net_income=D("2350000.00")
        ),
        schedules=["fixed_assets", "accrued_liabilities", "passed_adjustments"],
        tax_items=[
            TbHandoffTaxItemOut(
                key="passed_aje_3", label="Passed AJE-3", amount=PASSED_AJE_3, included=True
            ),
            TbHandoffTaxItemOut(
                key="income_tax_expense",
                label="Income tax expense",
                amount=D("750000.00"),
                included=False,
            ),
        ],
        preview_hash="0" * 63 + ("1" if chosen else "0"),
    )


def granite_peak_not_available() -> TbHandoffPreviewOut:
    """AUD-38 d (Wed Oct 21, 2026): before G8 the gate reads not released."""
    return granite_peak_preview(chosen=False).model_copy(
        update={"gate": "not_released", "status": "not_available"}
    )


def copperleaf_close_lock_landing() -> TbHandoffLandingOut:
    """TXP-02's banner on Copperleaf's 2026 Form 1120-S (CLS-12 c2): the same C12 landing, source
    `close_lock` (C-02)."""
    return TbHandoffLandingOut(
        handoff_id=_id("copperleaf-dec-2026-tb-v1"),
        source_kind="close_lock",
        locked_close_id=_id("copperleaf-close-2026-12"),
        source_label="TB from the December 2026 close, locked Jan 11, 2027",
        handed_off_at=datetime(2027, 1, 12, 14, 15, tzinfo=CT),
        handed_off_by="Priya Raman",
        source_link_allowed=True,
    )
