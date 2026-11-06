"""T-03-T07: TAX-13's Excel exports (T-03 §3 F5; ADR-042; DEC-2327).

Only the visible rows of the current view are written. The route holds the fresh second factor
(the matrix); the audit event names the tab and records the row count, never an amount. Workbooks
are openpyxl with pinned timestamps; every text cell is written as a string, never a formula.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

from openpyxl import Workbook

from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import estimates, extensions

_PINNED: Final = datetime(2000, 1, 1, tzinfo=UTC).replace(tzinfo=None)


def _book(
    title: str, header: list[str], rows: list[list[str | Decimal | date | int | None]]
) -> bytes:
    book = Workbook()
    book.properties.created = _PINNED
    book.properties.modified = _PINNED
    sheet = book.active
    if sheet is None:
        raise ValueError("a new workbook always has its first sheet")
    sheet.title = title
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    # Always a string: a client's name that starts "=" never becomes a formula.
    for cells in sheet.iter_rows(min_row=1):
        for cell in cells:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


async def _audit(ctx: AuthContext, action: str, count: int) -> None:
    async with uow(ctx.tenant) as tx:
        tx.record(
            action,
            target=Target("firm", ctx.tenant_id),
            after=Ref(rows=count),
        )


async def extensions_workbook(ctx: AuthContext, tax_year: int, segment: str | None) -> bytes:
    found = await extensions.rows(ctx, tax_year)
    if segment:
        found = [r for r in found if extensions.segment_of(r) == segment]
    rows: list[list[str | Decimal | date | int | None]] = [
        [
            r.client_name,
            line["jurisdiction"],
            line["form"],
            line["status"],
            line["original_due_on"],
            line["extended_due_on"],
            extensions.money(line["projected_liability"]),
            extensions.money(line["safe_harbor_target"]),
        ]
        for r in found
        for line in r.lines
    ]
    await _audit(ctx, "tax_schedule.extensions_exported", len(rows))
    return _book(
        "Extensions",
        [
            "Client",
            "Jurisdiction",
            "Form",
            "Status",
            "Original due",
            "Extended due",
            "Projected liability",
            "Safe-harbor target",
        ],
        rows,
    )


async def estimates_workbook(ctx: AuthContext, tax_year: int, quarter: int | None) -> bytes:
    found = await estimates.schedules(ctx, tax_year)
    rows: list[list[str | Decimal | date | int | None]] = [
        [s.client_name, s.form, s.method, q.quarter, q.due_on, q.amount, q.status, q.paid_on]
        for s in found
        for q in s.installments
        if quarter is None or q.quarter == quarter
    ]
    await _audit(ctx, "tax_schedule.estimates_exported", len(rows))
    return _book(
        "Estimates",
        ["Client", "Form", "Method", "Quarter", "Due", "Amount", "Status", "Paid on"],
        rows,
    )


__all__ = ["estimates_workbook", "extensions_workbook"]
