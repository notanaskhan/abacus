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
