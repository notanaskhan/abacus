"""The Ridgeline entity-depth slice (T-06-T07; TASK-8516; T-06 §5.3; SPEC-702 F1 to F4, F7):
Ridgeline Property Partners, LP's 2025 Form 1065 at E0 (Mon Sep 14, 2026, 9:24 AM CT), typed by the
T-06 contract models so a contract change fails here. Every figure is the TXP-03, TXP-08, TXP-09
and TAX-11 handoffs'. E3 computes the register from `depreciation.Asset` inputs (T-06-T13); this
slice holds the outputs the screens show. No database code."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Final

from abacus.modules.tax.api import entity_depth_contract as _contract

TaxDepthK1PreviewOut = _contract.TaxDepthK1PreviewOut
TaxDepthK1PreviewsOut = _contract.TaxDepthK1PreviewsOut
TaxDepthPartnerBasisOut = _contract.TaxDepthPartnerBasisOut
TaxDepthPropertyOut = _contract.TaxDepthPropertyOut
TaxDepthStateOut = _contract.TaxDepthStateOut
TaxDepthStatesOut = _contract.TaxDepthStatesOut

D = Decimal
RIDGELINE: Final = "Ridgeline Property Partners, LP"
SCHEDULE_K_LINE_2: Final = D("1231600")
_NS: Final = uuid.UUID("5f0c0600-0000-4000-8000-0000000e0600")


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


def properties() -> list[TaxDepthPropertyOut]:
    """TXP-03 b and Form 8825: land 3,600,000; depreciation 733,500."""
    return [
        TaxDepthPropertyOut(property_key="elm_street", name="Elm Street, Chicago",
                            land=D("1400000"), depreciation=D("169500")),
        TaxDepthPropertyOut(property_key="larimer", name="Larimer Lofts, Denver",
                            land=D("1300000"), depreciation=D("360000")),
        TaxDepthPropertyOut(property_key="bergen", name="Bergen Street, Brooklyn",
                            land=D("900000"), depreciation=D("204000")),
    ]  # fmt: skip


def states() -> TaxDepthStatesOut:
    """TXP-09 a: 46.0 + 31.5 + 22.5 = 100.0 on numerators 566,536 / 387,954 / 277,110 of 1,231,600;
    PTET 28,044 + 17,070 + 18,982 = 64,096 paid Mar 12, 2026."""
    paid = date(2026, 3, 12)
    rows = [
        ("IL", D("46.0"), D("28044")),
        ("CO", D("31.5"), D("17070")),
        ("NY", D("22.5"), D("18982")),
    ]
    return TaxDepthStatesOut(
        view="apportionment",
        states=[
            TaxDepthStateOut(state=s, apportionment_pct=pct, ptet="elected", ptet_paid=amount,
                             ptet_paid_on=paid, mapped=True)
            for s, pct, amount in rows
        ],
        apportionment_tally="tie",
        sourcing="proposed",
        paid_count=3,
        payable_count=3,
    )  # fmt: skip


APPORTIONMENT_NUMERATORS: Final = {"IL": D("566536"), "CO": D("387954"), "NY": D("277110")}


def k1_previews() -> TaxDepthK1PreviewsOut:
    """TAX-11 c: Σ box 2 = 1,231,600 = Schedule K line 2."""
    rows = [
        ("Ridgeline GP LLC", D("24632")),
        ("Meera Shah", D("468008")),
        ("Pell Street Ventures LLC", D("400270")),
        ("Pell Street II LLC", D("30790")),
        ("Jonah Feld", D("307900")),
    ]
    items = [TaxDepthK1PreviewOut(partner_id=_id(n), name=n, box_2=v) for n, v in rows]
    total = sum((i.box_2 for i in items), D("0"))
    return TaxDepthK1PreviewsOut(
        items=items,
        box_2_total=total,
        schedule_k_line_2=SCHEDULE_K_LINE_2,
        tally="tie" if total == SCHEDULE_K_LINE_2 else "off",
    )


def partner_basis() -> list[TaxDepthPartnerBasisOut]:
    """TXP-08 a: outside 17,943,095; Pell Street II off 28,595 pending §754."""
    rows = [
        ("Ridgeline GP LLC", D("314090"), D("314090")),
        ("Meera Shah", D("6727710"), D("6727710")),
        ("Pell Street Ventures LLC", D("5311350"), D("5311350")),
        ("Pell Street II LLC", D("885225"), D("913820")),
        ("Jonah Feld", D("4676125"), D("4676125")),
    ]
    return [
        TaxDepthPartnerBasisOut(partner_id=_id(n), name=n, inside=i, outside=o,
                                tally="tie" if i == o else "off")
        for n, i, o in rows
    ]  # fmt: skip


# --- TAX-11 form preview (T-06-T53, DEC-6035) ---------------------------------------------------

# The 2025 Form 1065 face's pages, then the attached forms in T-06-T49's order, each titled as
# its TY2025 face template titles it (the read's captions). Sch. C (M-3 filers) and Form 8916-A
# have no published face yet: placeholders.
TAX11_PAGES: Final = (
    ("p1", "Form 1065 page 1", False),
    ("p2", "Schedule B, page 2", False),
    ("p3", "Schedule B, page 3", False),
    ("p4", "Schedule K, page 4", False),
    ("p5", "Analysis of Net Income, Schedules L, M-1 and M-2, page 5", False),
    (
        "f8825_p1",
        "Form 8825 Rental Real Estate Income and Expenses of a Partnership or an S Corporation",
        False,
    ),
    ("f4562_p1", "Form 4562 Depreciation and Amortization (summary page)", False),
    (
        "f1065_m3_p1",
        "Schedule M-3 (Form 1065) page 1: Part I Financial Information and Net "
        "Income (Loss) Reconciliation",
        False,
    ),
    (
        "f1065_m3_p2",
        "Schedule M-3 (Form 1065) page 2: Part II Reconciliation of Net Income "
        "(Loss) per Income Statement With Income (Loss) per Return",
        False,
    ),
    (
        "f1065_m3_p3",
        "Schedule M-3 (Form 1065) page 3: Part III Reconciliation of Net Income "
        "(Loss) per Income Statement With Income (Loss) per Return—Expense/Deduction Items",
        False,
    ),
    ("f1065_m3_c_p1", "Sch. C (M-3 filers)", True),
    ("f8916_a_p1", "Form 8916-A", True),
    (
        "f1065_199a_stmt",
        "Section 199A information statement (Statement A: QBI pass-through entity reporting)",
        False,
    ),
    (
        "f1065_754_stmt",
        "Election under section 754 to adjust the basis of partnership property",
        False,
    ),
)
# Page 1's typed values (TAX-11 a; the EIN masked as the server sends it).
TAX11_PAGE1: Final = (
    ("a", "A Principal business activity", "Real estate rental"),
    ("b", "B Principal product or service", "Residential and commercial rentals"),
    ("c", "C Business code number", "531110"),
    ("name", "Name of partnership", RIDGELINE),
    ("d", "D Employer identification number", "••-•••0287"),
    ("e", "E Date business started", "01/15/2018"),
    ("f", "F Total assets", "17,914,500"),
    ("i", "I Number of Schedules K-1 attached", "5"),
)
# TAX-11 a: M-2 (a warning), Σ K-1 Item L and the §754 position (both blocking) fail.
TAX11_FAILING_E0: Final = frozenset(
    {"m2_line9_schedule_l21", "k1_item_l_schedule_l21", "section_754_statement"}
)


def tax11_preview() -> dict[str, object]:
    """TAX-11's reads at E0 (a, b, c) and after the fix and the §754 decision (d)."""
    from abacus.modules.tax.api import FORM_DIAGNOSTIC_RULES as RULES
    from abacus.modules.tax.api import form_diagnostic_title as rule_title
    from abacus_tools.synthetic.scenarios.brightwater_hale.entity_slice import SCHEDULE_K

    def diagnostics(failing: frozenset[str]) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for rule in RULES:
            fails = rule.key in failing
            out.append(
                {
                    "rule_key": rule.key,
                    "severity": ("blocking" if rule.severity == "blocking" else "warning")
                    if fails
                    else "clear",
                    "title": rule_title(rule.key, fails),
                    "page_key": "p5" if rule.key.startswith("m2") else None,
                }
            )
        return out

    schedule_k = [
        {"field_key": f"k_{line}", "label": f"{line} {label}", "value": f"{D(total):,.0f}"}
        for line, label, total, _shares in SCHEDULE_K
    ]
    return {
        "pages": [{"page_key": k, "caption": c, "placeholder": p} for k, c, p in TAX11_PAGES],
        "fields": {
            "p1": [{"field_key": k, "label": lb, "value": v} for k, lb, v in TAX11_PAGE1],
            "p4": schedule_k,
        },
        "diagnostics": {
            "e0": diagnostics(TAX11_FAILING_E0),
            "after_fix": diagnostics(frozenset()),
        },
        "k1": k1_previews().model_dump(mode="json"),
    }
