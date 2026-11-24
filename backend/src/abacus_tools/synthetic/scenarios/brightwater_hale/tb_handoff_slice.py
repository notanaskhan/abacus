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
TbHandoffSourceOut = _contract.TbHandoffSourceOut
TbHandoffTargetDetailOut = _contract.TbHandoffTargetDetailOut
TbHandoffScheduleOut = _contract.TbHandoffScheduleOut
TbHandoffMappingRowOut = _contract.TbHandoffMappingRowOut
TbHandoffCandidateOut = _contract.TbHandoffCandidateOut

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
# T-06-T45 (AUD-38 a, spec.md §1-§6): the fieldsets' words, the handoff's.
REVIEW_DETAIL: Final = {
    "2255": (
        "No prior-year account. Suggested: Schedule L, other current liabilities. Deduction "
        "timing under \u00a7461(h) is a tax judgment."
    ),
    "6875": (
        "Suggested: other deductions. Confirm the de minimis safe-harbor election (Treas. Reg. "
        "\u00a71.263(a)-1(f)) covers each item."
    ),
}
INDEPENDENCE: Final = (
    "Tax return preparation for an attest client is a permitted non-attest service, recorded in "
    "CLI-08 by Victor Hammond; Luis Ferrante acknowledged management's responsibilities in the "
    "tax engagement letter."
)
AJE_3_DETAIL: Final = (
    "Front Range Freight Co. invoice FRF-30418, June inbound freight, 68,400, recorded by the "
    "client in July. All events occurred in FY2026, so it is deductible in FY2026 although not "
    "booked: candidate M-1 deduction (68,400). Timing."
)
TAX_EXPENSE_DETAIL: Final = (
    "Book tax, added back on Schedule M-1; deferred taxes stay in the provision workpaper."
)


def _schedule_rows() -> list[TbHandoffScheduleOut]:
    opening, additions, depreciation = PPE
    closing = opening + additions - depreciation  # 6,380,000, by code
    return [
        TbHandoffScheduleOut(
            key="fixed_assets",
            label="Fixed assets",
            detail=(
                f"{opening:,.0f} + additions {additions:,.0f} \u2212 depreciation "
                f"{depreciation:,.0f} = {closing:,.0f} \u2192 Form 4562 and the depreciation M-1"
            ),
        ),
        TbHandoffScheduleOut(
            key="accrued_liabilities",
            label="Accrued liabilities",
            detail=(
                f"{ACCRUED_LIABILITIES:,.0f} at Jun 30, 2026 \u2192 \u00a7461(h) economic "
                "performance and \u00a7404(a)(5) 2\u00bd-month review"
            ),
        ),
        TbHandoffScheduleOut(
            key="passed_adjustments",
            label="Passed adjustments",
            detail=(
                f"AJE-3 {PASSED_AJE_3:,.0f} (SUM; declined by the client Oct 5) \u2192 M-1 "
                "candidate"
            ),
        ),
    ]


def granite_peak_accounts() -> list[TbHandoffMappingRowOut]:
    """The O4 table's 128 rows: Granite Peak's FY2026 accounts (AUD-31's TB) with the two review
    accounts in place of the last two expense accounts; 121 travel from the prior-year mapping,
    5 as suggestions, 2 blank. Tax codes travel only where the server holds them (none here)."""
    from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_content import (
        granite_accounts,
    )

    accounts = granite_accounts()[:126]
    rows = [
        TbHandoffMappingRowOut(
            account_ref=a.account_code,
            account_name=a.account_name,
            balance=a.debit - a.credit,
            source="firm_mapping" if n < 121 else "tb_mapper",
        )
        for n, a in enumerate(accounts)
    ]
    rows += [
        TbHandoffMappingRowOut(account_ref=ref, account_name=name, balance=bal, source="blank")
        for ref, name, bal in REVIEW_ACCOUNTS
    ]
    return sorted(rows, key=lambda r: r.account_ref)


def granite_peak_preview(*, chosen: bool) -> TbHandoffPreviewOut:
    """AUD-38 b (`chosen=False`, 10:12 AM) or a (`chosen=True`, both Send blank, 10:29 AM)."""
    reviews = [
        TbHandoffReviewAccountOut(
            account_ref=ref,
            account_name=name,
            balance=balance,
            choice="send_blank" if chosen else None,
            source="tb_mapper",
            detail=REVIEW_DETAIL[ref],
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
                key="passed_aje_3",
                label="Passed AJE-3",
                amount=PASSED_AJE_3,
                included=True,
                detail=AJE_3_DETAIL,
            ),
            TbHandoffTaxItemOut(
                key="income_tax_expense",
                label="Income tax expense",
                amount=D("750000.00"),
                included=False,
                detail=TAX_EXPENSE_DETAIL,
            ),
        ],
        preview_hash="0" * 63 + ("1" if chosen else "0"),
        source=TbHandoffSourceOut(
            engagement_label=f"{GRANITE_PEAK} \u00b7 FY2026 FS audit",
            tb_label="Final TB \u00b7 year ended Jun 30, 2026",
            released_on=RELEASED_ON,
            released_by="Margaret Okonkwo",
            balanced=True,
        ),
        target=TbHandoffTargetDetailOut(
            return_label=f"{TARGET_RETURN} \u00b7 {GRANITE_PEAK}",
            return_detail="2025 Form 1120 for the fiscal year Jul 1, 2025 \u2013 Jun 30, 2026",
            engagement_created_on=datetime(2026, 10, 12, tzinfo=CT),
            extension_filed_on=datetime(2026, 10, 13, tzinfo=CT),
            due_on=datetime(2027, 4, 15, tzinfo=CT),
            team=[
                f"{TAX_TEAM[0]} (preparer)",
                f"{TAX_TEAM[1]} (reviewer)",
                f"{TAX_TEAM[2]} (partner)",
            ],
        ),
        schedule_rows=_schedule_rows(),
        accounts=granite_peak_accounts(),
        independence=INDEPENDENCE,
    )


def granite_peak_not_available() -> TbHandoffPreviewOut:
    """AUD-38 d (Wed Oct 21, 2026): before G8 the gate reads not released."""
    return granite_peak_preview(chosen=False).model_copy(
        update={"gate": "not_released", "status": "not_available"}
    )


def granite_peak_superseded() -> TbHandoffPreviewOut:
    """AUD-38 e (illustrative): the audited TB changed after release (AUD-30); handing off again
    replaces the Nov 9 version (version 1 is current)."""
    return granite_peak_preview(chosen=True).model_copy(
        update={"gate": "superseded", "status": "superseded", "current_version_no": 1}
    )


def granite_peak_landing() -> TbHandoffLandingOut:
    """TXP-13 d (Mon Nov 9, 2026, 11:00 AM): the FY2026 Form 1120's landing after the hand-off."""
    return TbHandoffLandingOut(
        handoff_id=_id("granite-peak-fy2026-tb-v1"),
        source_kind="audit_release",
        source_label="FY2026 audit",
        handed_off_at=HANDED_OFF_AT,
        handed_off_by="Hannah Leclerc",
        source_link_allowed=True,
        book_income=TbHandoffBookIncomeOut(
            pretax=D("3100000.00"), income_tax_expense=D("750000.00"), net_income=D("2350000.00")
        ),
        counts=TbHandoffCountsOut(mapped=121, suggested=5, review=2, total=128),
        candidates=[TbHandoffCandidateOut(ref="AJE-3", amount=-PASSED_AJE_3)],
        source_work_item_id=_id("granite-peak-fy2026-audit"),
    )


def aud38_rows() -> dict[str, object]:
    """AUD-38 a-e and TXP-13 d, JSON-ready (`scenario.aud38.json`)."""
    return {
        "preview_ready": granite_peak_preview(chosen=True).model_dump(mode="json"),
        "preview_needs_review": granite_peak_preview(chosen=False).model_dump(mode="json"),
        "preview_not_available": granite_peak_not_available().model_dump(mode="json"),
        "preview_superseded": granite_peak_superseded().model_dump(mode="json"),
        "landing": granite_peak_landing().model_dump(mode="json"),
        "target": {
            "target_work_item_id": str(_id("granite-peak-fy2026-1120")),
            "return_label": TARGET_RETURN,
            "tax_year": 2025,
        },
        "handed_off_at": HANDED_OFF_AT.isoformat(),
    }


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
