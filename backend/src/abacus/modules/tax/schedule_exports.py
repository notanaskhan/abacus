"""TAX-13's Open in Excel (T-03-T07; DEC-2350): the viewer's visible rows of the current segment.
Client strings are written as text, never formulas (ADR-052). The audit event carries the row count
only: no name or amount."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from io import BytesIO
from typing import Final, cast

from openpyxl import Workbook
from openpyxl.cell.cell import Cell as Cell_

from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import estimates as est
from abacus.modules.tax import extensions as ext

XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
Cell = str | int | Decimal | None


def _book(title: str, header: Sequence[str], rows: Sequence[Sequence[Cell]]) -> bytes:
    book = Workbook()
    sheet = book.active
    if sheet is None:  # a new Workbook always has its first sheet
        sheet = book.create_sheet()
    sheet.title = title
    sheet.append(list(header))
    for row in rows:
        at = sheet.max_row + 1
        for col, value in enumerate(row, start=1):
            cell = cast(Cell_, sheet.cell(row=at, column=col))
            cell.value = value
            if isinstance(value, str):
                cell.data_type = "s"  # a client's "=..." stays text (ADR-052)
            elif isinstance(value, Decimal):
                cell.number_format = "#,##0.00"
    out = BytesIO()
    book.save(out)
    return out.getvalue()


async def _audited(ctx: AuthContext, action: str, count: int) -> None:
    async with uow(ctx.tenant) as tx:
        tx.record(action, target=Target("tenant", ctx.tenant_id), after=Ref(rows=count))


async def extensions(ctx: AuthContext, tax_year: int, segment: str | None) -> tuple[bytes, str]:
    found = [r for r in await ext.rows(ctx, tax_year) if ext.in_segment(r, segment)]
    rows: list[list[Cell]] = []
    for r in found:
        for line in r.lines:
            paid = ext.line_check(r.tax_return_id, line, r.payments, tax_year)
            rows.append(
                [
                    r.client_name,
                    r.return_form,
                    str(line["form"]),
                    str(line["jurisdiction"]),
                    str(line["status"]),
                    str(line["extended_due_on"]),
                    paid.projected_liability,
                    paid.target,
                    paid.paid,
                ]
            )
    await _audited(ctx, "tax_schedule.extensions_exported", len(rows))
    data = _book(
        "Extensions",
        (
            "Client",
            "Return",
            "Form",
            "Jurisdiction",
            "Status",
            "Extended due",
            "Projected liability",
            "Safe-harbor target",
            "Paid by original due",
        ),
        rows,
    )
    return data, f"extensions-{tax_year}.xlsx"


async def estimates(ctx: AuthContext, tax_year: int, quarter: int | None) -> tuple[bytes, str]:
    found = await est.rows(ctx, tax_year)
    rows: list[list[Cell]] = []
    for r in found:
        for i in r.installments:
            if quarter is not None and i["quarter"] != quarter:
                continue
            rows.append(
                [
                    r.client_name,
                    str(r.schedule["form"]),
                    str(r.schedule["jurisdiction"]),
                    int(i["quarter"]),
                    str(i["due_on"]),
                    est.money(i["amount"]),
                    str(i["status"]),
                ]
            )
    await _audited(ctx, "tax_schedule.estimates_exported", len(rows))
    data = _book(
        "Estimates",
        ("Client", "Form", "Jurisdiction", "Quarter", "Due", "Amount", "Status"),
        rows,
    )
    return data, f"estimates-{tax_year}.xlsx"
