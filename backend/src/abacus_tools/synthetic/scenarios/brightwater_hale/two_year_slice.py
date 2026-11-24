"""The Feld two-year comparison slice (T-08-T22; TASK-8936; DEC-5938; TAX-10 a-e, x1): Jonah &
Claire Feld's 2025 Form 1040 against 2024 at Mon Sep 14, 2026, 10:05 AM CT, typed by the T-08
contract so a contract change fails here. Every label, figure and explanation is the TAX-10
handoff's (spec.md ROWS); the differences and percentages are computed here by code (ADR-050),
never typed, and the flags follow the firm threshold (> $1,000 and > 10%, 1040 Review Checklist
v6). No database code: the service (T-08-T11) reads the return's summaries.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from abacus.modules.tax.api import practice_tools_contract as _c
from abacus.modules.tax.api import two_year_lines as _lines
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT

D = Decimal
_NS: Final = uuid.UUID("5f0c0810-0000-4000-8000-0000000a1010")  # T-08 two-year
THRESHOLD_AMOUNT: Final = D("1000")
THRESHOLD_PCT: Final = D("10")
ACCEPTED_AT: Final = datetime(2026, 9, 14, 9, 52, tzinfo=CT)
ACCEPTED_AT_SCH_A_11: Final = datetime(2026, 9, 14, 10, 7, tzinfo=CT)
Group = Literal["income", "deductions", "tax_and_payments"]
Total = Literal["total", "grand"] | None


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


# (group, ref, label, 2024, 2025, total, explanation, citation, initially accepted)
ROWS: Final[tuple[tuple[Group, str, str, str, str, Total, str | None, str | None, bool], ...]] = (
    ("income", "1a", "Wages, salaries, tips", "251000", "268400", None, None, None, False),
    ("income", "2a", "Tax-exempt interest", "1400", "1550", None, None, None, False),
    ("income", "2b", "Taxable interest", "6100", "6910", None, None, None, False),
    ("income", "3a", "Qualified dividends", "10610", "11960", None,
     "Halvard dividends up on the same holdings; no new accounts (1099-DIV box 1b)", "1099-DIV",
     True),
    ("income", "3b", "Ordinary dividends", "13240", "14820", None,
     "Halvard 1099-DIV box 1a; same holdings as 2024", "1099-DIV", True),
    ("income", "Sch 1 line 5", "Rental real estate, royalties, partnerships (Ridgeline)",
     "281600", "307900", None, None, None, False),
    ("income", "9", "Total income", "551940", "598030", "total", None, None, False),
    ("income", "11", "Adjusted gross income", "551940", "598030", "total", None, None, False),
    ("deductions", "Sch A 5e", "State and local taxes (capped)", "10000", "10591", None, None,
     None, False),
    ("deductions", "Sch A 8a", "Home mortgage interest", "18960", "18240", None, None, None,
     False),
    ("deductions", "Sch A 11", "Gifts by cash or check", "11000", "12500", None,
     "Six 2025 receipts total 12,500 (Feld_2025_Donations.pdf); new gift: Mercer Hill Health "
     "Foundation 2,500", "Donations", False),
    ("deductions", "12", "Itemized deductions", "39960", "41331", "total", None, None, False),
    ("deductions", "13", "Qualified business income deduction", "56320", "61580", None, None,
     None, False),
    ("deductions", "15", "Taxable income", "455660", "495119", "total", None, None, False),
    ("tax_and_payments", "16", "Tax", "99381", "110531", None,
     "Schedule E +26,300 and wages +17,400 leave 88,559 of ordinary income in the 32% bracket "
     "(2024: 61,150); qualified dividends stay at 15%", "Sch E", True),
    ("tax_and_payments", "23", "Other taxes (Schedule 2)", "11445", "12692", None,
     "NIIT +1,090 on higher passive rental income; Additional Medicare Tax +157 on wages over "
     "$250,000", "W-2", True),
    ("tax_and_payments", "24", "Total tax", "110826", "123223", "total",
     "Line 16 +11,150 and line 23 +1,247", "Sch 2", True),
    ("tax_and_payments", "25d", "Federal income tax withheld", "49600", "53476", None, None,
     None, False),
    ("tax_and_payments", "26", "Estimated tax payments", "56000", "60000", None, None, None,
     False),
    ("tax_and_payments", "Sch 3 line 10", "Amount paid with extension", "6400", "10000", None,
     "Sized on the April projection while the Ridgeline K-1 was outstanding (Form 4868, Apr 14)",
     "Form 4868", True),
    ("tax_and_payments", "33", "Total payments", "112000", "123476", "total",
     "Withholding +3,876, estimates +4,000, extension payment +3,600", "W-2", True),
    ("tax_and_payments", "34", "Overpaid / refund", "1174", "253", "grand", None, None, False),
)  # fmt: skip


def pct(prior: Decimal, current: Decimal) -> Decimal | None:
    if prior == 0:
        return None
    return ((current - prior) * 100 / abs(prior)).quantize(D("0.1"), rounding=ROUND_HALF_UP)


def flagged(prior: Decimal, current: Decimal) -> tuple[bool, str | None]:
    """Over the firm threshold when both > $1,000 and > 10%; a percent over 10 below $1,000 is
    not flagged and says why."""
    delta, p = current - prior, pct(prior, current)
    over_pct = p is not None and abs(p) > THRESHOLD_PCT
    if over_pct and abs(delta) > THRESHOLD_AMOUNT:
        return True, None
    return False, ("below_amount" if over_pct else None)


State = Literal["a", "b", "c", "d", "e", "x1"]


def feld_two_year(state: State = "a") -> _c.TaxPracticeTwoYearOut:
    """a default (7 of 8), b the Over threshold filter, c all accepted (8 of 8), d before the
    agent ran (Sep 9, 0 of 8), e an explain run in flight, x1 agents off for this taxpayer."""
    lines: list[_c.TaxPracticeTwoYearLineOut] = []
    codes = {_lines.LINE_REFS[code]: (code, text_) for code, text_ in _lines.LINE_MAPS["1040"]}
    for group, ref, _label, before, after, total, text, cite, accepted in ROWS:
        prior, current = D(before), D(after)
        flag, below = flagged(prior, current)
        key, label = codes[ref]  # the live line map's code and label (CPA-reviewed, OQ-15)
        if not flag or state in ("d", "e", "x1"):
            explained = None
        else:
            explained = "accepted" if accepted or state == "c" else "proposed"
        acc_at = (
            None
            if explained != "accepted"
            else ACCEPTED_AT_SCH_A_11
            if ref == "Sch A 11"
            else ACCEPTED_AT
        )
        lines.append(
            _c.TaxPracticeTwoYearLineOut(
                line_key=key,
                label=label,
                line_ref=ref,
                group=group,
                total=total,
                current=current,
                prior=prior,
                delta=current - prior,
                delta_pct=pct(prior, current),
                flagged=flag,
                below_reason=below,
                state=("unexplained" if flag else None) if explained is None else explained,
                explanation=text if explained is not None else None,
                explanation_version_id=_id(f"explanation:{key}") if explained else None,
                author_kind="agent" if explained else None,
                citations=(
                    []
                    if explained is None or cite is None
                    else [
                        _c.TaxPracticeCitationOut(
                            citation_id=_id(f"cite:{key}"), label=cite, verified=True
                        )
                    ]
                ),
                accepted_by_initials="SI" if explained == "accepted" else None,
                accepted_at=acc_at,
                values_hash=hashlib.sha256(f"{key}:{before}:{after}".encode()).hexdigest(),
                allowed_actions=(
                    ["two_year.edit", "two_year.accept"]
                    if explained == "proposed"
                    else ["two_year.edit"]
                    if flag
                    else []
                ),
            )
        )
    by_ref = {ln.line_ref: ln for ln in lines}
    over = sum(1 for ln in lines if ln.flagged)
    return _c.TaxPracticeTwoYearOut(
        tax_return_id=_id("feld-2025-1040"),
        current_summary_id="feld-2025-1040:summary:v3",
        filter="over_threshold" if state == "b" else "all",
        threshold=_c.TaxPracticeTwoYearThresholdOut(
            source="checklist_parameter",
            source_label="1040 Review Checklist v6",
            version_id=_id("checklist:1040:v6"),
            amount=THRESHOLD_AMOUNT,
            percent=THRESHOLD_PCT,
        ),
        lines=[ln for ln in lines if ln.flagged] if state == "b" else lines,
        agi=by_ref["11"].current,
        agi_delta_pct=by_ref["11"].delta_pct,
        total_tax=by_ref["24"].current,
        total_tax_delta_pct=by_ref["24"].delta_pct,
        refund=by_ref["34"].current,
        prior_refund=by_ref["34"].prior,
        over_threshold=over,
        accepted=sum(1 for ln in lines if ln.state == "accepted"),
        explain_available=state != "x1",
        allowed_actions=["two_year.explain"] if state != "x1" else [],
        explaining=state == "e",
        explain_unavailable_reason="agents_off_for_taxpayer" if state == "x1" else None,
    )


def tax10_rows() -> dict[str, object]:
    """TAX-10 a-e and x1, JSON-ready (`scenario.tax10.json`)."""
    states: tuple[State, ...] = ("a", "b", "c", "d", "e", "x1")
    return {s: feld_two_year(s).model_dump(mode="json") for s in states}
