"""C-02-T28 (TASK-8814; SPEC-701 F7): CLS-08's package render.

Row acceptance: "Two renders of the same posted TB are byte-identical, every page carries 'No
assurance is provided.' for August and none does for the illustrative December package." Here,
on the pure composition: the same package composes the same blocks and the XLSX is byte-stable;
an AR-C 70 package carries the legend block (C11 repeats a legend on every page) and a CAS
by-product carries none; commentary edits are composed as written.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from abacus.modules.closes.delivery_contract import DeliveryPackageOut, DeliveryStatementLineOut
from abacus.modules.closes.package_render import (
    NO_ASSURANCE,
    compose_package,
    package_workbook,
    period_label,
)


def _package(legend: str | None, route: str) -> DeliveryPackageOut:
    return DeliveryPackageOut(
        close_id=uuid4(),
        status="draft",
        version_no=2,
        route=cast(Any, route),  # Any: a route literal the model narrows
        legend=legend,
        sections=["balance_sheet", "income_statement", "commentary"],
        cas_answer=True,
        balance_sheet=[
            DeliveryStatementLineOut(
                key="current_assets", label="Total current assets", amount=Decimal("337135.45")
            ),
            DeliveryStatementLineOut(
                key="total_assets", label="Total assets", amount=Decimal("549195.45")
            ),
        ],
        income_statement=[
            DeliveryStatementLineOut(
                key="revenue",
                label="Revenue",
                amount=Decimal("214600.00"),
                prior=Decimal("205360.00"),
            ),
            DeliveryStatementLineOut(
                key="net_income",
                label="Net income",
                amount=Decimal("27795.00"),
                prior=Decimal("31455.00"),
            ),
        ],
        commentary="Revenue rose 4.5% to $214,600.\n\nPayroll rose 12.5% to $68,910.",
        preconditions=[],
        content_hash="0" * 64,
        version=2,
    )


def test_ac_the_same_package_composes_the_same_document() -> None:
    a = compose_package(
        _package(NO_ASSURANCE, "ar_c_70_preparation"),
        "Copperleaf Coffee Roasters, Inc.",
        period_label("2026-08"),
        page_numbers=True,
    )
    b = compose_package(
        _package(NO_ASSURANCE, "ar_c_70_preparation"),
        "Copperleaf Coffee Roasters, Inc.",
        period_label("2026-08"),
        page_numbers=True,
    )
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    pkg = _package(NO_ASSURANCE, "ar_c_70_preparation")
    assert package_workbook(pkg, "Copperleaf") == package_workbook(pkg, "Copperleaf")


def test_ac_august_carries_the_legend_and_december_none() -> None:
    august = compose_package(
        _package(NO_ASSURANCE, "ar_c_70_preparation"),
        "C",
        period_label("2026-08"),
        page_numbers=True,
    )
    december = compose_package(
        _package(None, "cas_by_product"), "C", period_label("2026-12"), page_numbers=True
    )
    assert {"type": "legend", "text": "No assurance is provided."} in august
    assert not [
        b
        for b in december
        if isinstance(b, dict) and cast(dict[str, object], b).get("type") == "legend"
    ]
    assert period_label("2026-08") == "As of and for the month ended August 31, 2026"


def test_commentary_is_composed_as_the_person_left_it() -> None:
    blocks = compose_package(
        _package(NO_ASSURANCE, "ar_c_70_preparation"), "C", "p", page_numbers=False
    )
    paragraphs = [cast(dict[str, Any], b) for b in blocks if isinstance(b, dict)]  # Any: blocks
    texts = [
        str(r["text"])
        for b in paragraphs
        if b.get("type") == "paragraph"
        for r in cast(list[dict[str, object]], b["runs"])
    ]
    assert "Payroll rose 12.5% to $68,910." in texts
